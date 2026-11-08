"""Entraînement d'une machine de Born quantique (QCBM) en simulation.

Le modèle est la distribution de mesure p(θ) d'un ansatz ; on l'ajuste à une
distribution cible t (vecteur de 2^n probabilités, convention little-endian
de Qiskit, voir ``distributions``).

Pertes :

- ``"kl"`` : divergence de Kullback-Leibler KL(t ‖ p) = Σ t log(t / (p + ε)) ;
- ``"mmd"`` : écart moyen maximal au carré (Liu et Wang 2018, arXiv:1804.04168),
  MMD² = (p - t)ᵀ K (p - t), noyau gaussien sur la distance de Hamming entre
  chaînes de bits, mélange de bandes passantes σ² ∈ {0,25 ; 1 ; 4} ;
- ``"tvd"`` : distance en variation totale ½ Σ |p - t|, non dérivable.

Gradients exacts par la règle du décalage de paramètre appliquée aux
probabilités, ∂p/∂θ_k = (p(θ + π/2·e_k) - p(θ - π/2·e_k)) / 2, puis règle de
la chaîne pour KL et MMD. Avec ``"tvd"``, seuls SPSA et COBYLA sont permis.
"""

from collections.abc import Callable

import numpy as np
from qiskit import QuantumCircuit

from .distributions import check_probabilities
from .gradients import batched_probabilities

EPSILON = 1e-12
MMD_SIGMAS = (0.25, 1.0, 4.0)
LOSSES = ("kl", "tvd", "mmd")
OPTIMIZERS = ("adam", "spsa", "cobyla")

# Lots de simulation bornés (amplitudes simulées en même temps).
_MAX_BATCH_AMPLITUDES = 2**21


def hellinger(p: np.ndarray, q: np.ndarray) -> float:
    """Distance de Hellinger : sqrt(1 - Σ sqrt(p q)), entre 0 et 1."""
    return float(np.sqrt(max(0.0, 1.0 - np.sqrt(p * q).sum())))


def distribution_metrics(target: np.ndarray, probs: np.ndarray) -> dict:
    """KL(cible ‖ modèle), TVD et distance de Hellinger entre deux distributions."""
    target = np.asarray(target, dtype=float)
    probs = np.asarray(probs, dtype=float)
    mask = target > 0
    return {
        "kl": float((target[mask] * np.log(target[mask] / (probs[mask] + EPSILON))).sum()),
        "tvd": float(0.5 * np.abs(probs - target).sum()),
        "hellinger": hellinger(target, probs),
    }


def mmd_kernel(n_qubits: int, sigmas: tuple[float, ...] = MMD_SIGMAS) -> np.ndarray:
    """Noyau gaussien (mélange de bandes passantes) sur la distance de Hamming, (2^n, 2^n)."""
    states = np.arange(2**n_qubits)
    bits = (states[:, None] >> np.arange(n_qubits)) & 1
    distance = (bits[:, None, :] != bits[None, :, :]).sum(axis=2)
    return np.mean([np.exp(-distance / (2 * s)) for s in sigmas], axis=0)


def loss_value(loss: str, probs: np.ndarray, target: np.ndarray, kernel: np.ndarray | None = None) -> float:
    """Valeur de la perte ``loss`` pour les probabilités du modèle ``probs``."""
    if loss == "kl":
        mask = target > 0
        return float((target[mask] * np.log(target[mask] / (probs[mask] + EPSILON))).sum())
    if loss == "tvd":
        return float(0.5 * np.abs(probs - target).sum())
    if loss == "mmd":
        diff = probs - target
        return float(diff @ kernel @ diff)
    raise ValueError(f"Perte inconnue : {loss!r} (kl, tvd ou mmd attendu).")


def _loss_derivative(loss: str, probs: np.ndarray, target: np.ndarray, kernel: np.ndarray | None) -> np.ndarray:
    """∂perte/∂p (KL et MMD seulement)."""
    if loss == "kl":
        return -target / (probs + EPSILON)
    if loss == "mmd":
        return 2 * kernel @ (probs - target)
    raise ValueError("La TVD n'est pas dérivable : utilisez SPSA ou COBYLA.")


class _Model:
    """Évalue p(θ), exactement ou par tirages, sur des lots bornés."""

    def __init__(self, ansatz: QuantumCircuit, shots: int | None, rng: np.random.Generator):
        self.ansatz = ansatz
        self.shots = shots
        self.rng = rng
        self.size = 2**ansatz.num_qubits

    def exact(self, thetas: np.ndarray) -> np.ndarray:
        thetas = np.atleast_2d(thetas)
        chunk = max(1, _MAX_BATCH_AMPLITUDES // self.size)
        return np.concatenate([batched_probabilities(self.ansatz, thetas[i : i + chunk]) for i in range(0, len(thetas), chunk)])

    def estimate(self, thetas: np.ndarray) -> np.ndarray:
        exact = self.exact(thetas)
        if self.shots is None:
            return exact
        exact = np.clip(exact, 0, None)
        exact /= exact.sum(axis=1, keepdims=True)
        return np.array([self.rng.multinomial(self.shots, p) / self.shots for p in exact])


def loss_and_gradient(
    ansatz: QuantumCircuit,
    target: np.ndarray,
    theta: np.ndarray,
    loss: str,
    kernel: np.ndarray | None = None,
    model: _Model | None = None,
) -> tuple[float, np.ndarray]:
    """Perte et gradient exact (règle du décalage sur les probabilités) au point ``theta``."""
    theta = np.asarray(theta, dtype=float)
    n_params = theta.size
    model = model or _Model(ansatz, None, np.random.default_rng(0))
    shifts = np.zeros((2 * n_params, n_params))
    shifts[0::2][np.diag_indices(n_params)] = np.pi / 2
    shifts[1::2][np.diag_indices(n_params)] = -np.pi / 2
    batch = np.vstack([theta[None, :], theta[None, :] + shifts])
    probs = model.estimate(batch)
    current = probs[0]
    dp = (probs[1::2] - probs[2::2]) / 2  # (P, 2^n)
    gradient = dp @ _loss_derivative(loss, current, target, kernel)
    return loss_value(loss, current, target, kernel), gradient


def train_qcbm(
    ansatz: QuantumCircuit,
    target,
    loss: str = "kl",
    optimizer: str = "adam",
    max_iter: int = 200,
    learning_rate: float = 0.1,
    shots: int | None = None,
    seed: int | None = None,
    callback: Callable[[int, float], None] | None = None,
) -> dict:
    """Entraîne un ansatz à reproduire la distribution ``target``.

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit paramétré (portes paramétrées RX, RY ou RZ d'angle égal à un paramètre).
    target : vecteur de 2^n probabilités
        Distribution cible, n étant le nombre de qubits de l'ansatz.
    loss : str
        ``"kl"``, ``"mmd"`` ou ``"tvd"`` (voir la docstring du module).
    optimizer : str
        ``"adam"`` (gradient exact, β1 = 0,9, β2 = 0,999), ``"spsa"``
        (perturbations simultanées, gains a_k = lr / (k + 1 + A)^0,602 avec
        A = max_iter / 10, et c_k = 0,2 / (k + 1)^0,101) ou ``"cobyla"``
        (``scipy.optimize``, rayon initial ``learning_rate``).
    max_iter : int
        Nombre d'itérations (d'évaluations de la perte pour COBYLA).
    learning_rate : float
        Pas d'Adam, gain de SPSA, rayon initial de COBYLA.
    shots : int ou None
        None : probabilités exactes ; sinon, probabilités estimées par
        ``shots`` tirages (``default_rng(seed)``) pendant l'entraînement.
    seed : int ou None
        Graine des paramètres initiaux (uniformes dans [0, 2π]), des tirages et de SPSA.
    callback : callable ou None
        Appelée avec ``(itération, perte)`` après chaque itération.

    Retourne
    --------
    dict
        ``params`` (paramètres finaux, ordre de ``ansatz.parameters``),
        ``history`` (perte à chaque itération), ``probabilities``
        (distribution finale exacte), ``metrics`` (KL, TVD et Hellinger,
        calculés sur les probabilités exactes), ``loss``, ``optimizer``,
        ``n_iterations``, ``n_parameters``.

    Lève
    ----
    ValueError
        Perte ou optimiseur inconnu, TVD avec Adam, cible invalide ou de
        taille différente de 2^n.
    """
    if loss not in LOSSES:
        raise ValueError(f"Perte inconnue : {loss!r} (kl, tvd ou mmd attendu).")
    if optimizer not in OPTIMIZERS:
        raise ValueError(f"Optimiseur inconnu : {optimizer!r} (adam, spsa ou cobyla attendu).")
    if loss == "tvd" and optimizer == "adam":
        raise ValueError("La TVD n'est pas dérivable : avec la perte « tvd », utilisez SPSA ou COBYLA.")
    if max_iter < 1:
        raise ValueError("max_iter doit valoir au moins 1.")
    if shots is not None and shots < 1:
        raise ValueError("shots doit être None ou un entier strictement positif.")
    target = check_probabilities(target)
    if target.size != 2**ansatz.num_qubits:
        raise ValueError(f"La cible a {target.size} états, l'ansatz en produit {2**ansatz.num_qubits}.")
    n_params = ansatz.num_parameters
    if n_params == 0:
        raise ValueError("L'ansatz n'a aucun paramètre libre.")

    rng = np.random.default_rng(seed)
    theta = rng.uniform(0, 2 * np.pi, n_params)
    model = _Model(ansatz, shots, rng)
    kernel = mmd_kernel(ansatz.num_qubits) if loss == "mmd" else None
    history: list[float] = []

    def record(value: float) -> None:
        history.append(float(value))
        if callback is not None:
            callback(len(history), float(value))

    if optimizer == "adam":
        m = np.zeros(n_params)
        v = np.zeros(n_params)
        beta1, beta2, eps = 0.9, 0.999, 1e-8
        for k in range(1, max_iter + 1):
            value, gradient = loss_and_gradient(ansatz, target, theta, loss, kernel, model)
            m = beta1 * m + (1 - beta1) * gradient
            v = beta2 * v + (1 - beta2) * gradient**2
            theta = theta - learning_rate * (m / (1 - beta1**k)) / (np.sqrt(v / (1 - beta2**k)) + eps)
            record(value)
    elif optimizer == "spsa":
        stability = max_iter / 10
        for k in range(max_iter):
            a_k = learning_rate / (k + 1 + stability) ** 0.602
            c_k = 0.2 / (k + 1) ** 0.101
            delta = rng.choice([-1.0, 1.0], size=n_params)
            probs = model.estimate(np.vstack([theta + c_k * delta, theta - c_k * delta]))
            plus = loss_value(loss, probs[0], target, kernel)
            minus = loss_value(loss, probs[1], target, kernel)
            theta = theta - a_k * (plus - minus) / (2 * c_k) * delta
            record((plus + minus) / 2)
    else:
        from scipy.optimize import minimize

        def objective(x: np.ndarray) -> float:
            value = loss_value(loss, model.estimate(x)[0], target, kernel)
            if len(history) < max_iter:
                record(value)
            return value

        result = minimize(objective, theta, method="COBYLA", options={"maxiter": max_iter, "rhobeg": learning_rate})
        theta = np.asarray(result.x, dtype=float)

    final = model.exact(theta)[0]
    return {
        "params": theta.tolist(),
        "history": history,
        "probabilities": final.tolist(),
        "metrics": distribution_metrics(target, final),
        "loss": loss,
        "optimizer": optimizer,
        "n_iterations": len(history),
        "n_parameters": n_params,
    }
