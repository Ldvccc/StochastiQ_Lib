import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.quantum_info import Operator

# Seuil de variance sous lequel un paramètre est compté comme inactif.
INACTIVE_THRESHOLD = 1e-12

# Nombre maximal d'amplitudes simulées simultanément (borne la mémoire).
_MAX_BATCH_AMPLITUDES = 2**21

_ROTATIONS = {"rx", "ry", "rz"}


def _rotation_matrices(name: str, angles: np.ndarray) -> np.ndarray:
    """Matrices (B, 2, 2) de RX, RY ou RZ pour un lot d'angles."""
    c, s = np.cos(angles / 2), np.sin(angles / 2)
    m = np.zeros((len(angles), 2, 2), dtype=complex)
    if name == "rx":
        m[:, 0, 0] = m[:, 1, 1] = c
        m[:, 0, 1] = m[:, 1, 0] = -1j * s
    elif name == "ry":
        m[:, 0, 0] = m[:, 1, 1] = c
        m[:, 0, 1], m[:, 1, 0] = -s, s
    else:
        m[:, 0, 0], m[:, 1, 1] = np.exp(-0.5j * angles), np.exp(0.5j * angles)
    return m


def _apply_batched_1q(states: np.ndarray, matrices: np.ndarray, axis: int) -> np.ndarray:
    s = np.moveaxis(states, axis, -1)
    s = np.einsum("b...j,bij->b...i", s, matrices)
    return np.moveaxis(s, -1, axis)


def _apply_fixed(states: np.ndarray, matrix: np.ndarray, axes: list[int]) -> np.ndarray:
    k = len(axes)
    m = matrix.reshape((2,) * (2 * k))
    s = np.tensordot(m, states, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(s, list(range(k)), axes)


def _expectations(ansatz: QuantumCircuit, thetas: np.ndarray, z_qubits: list[int]) -> np.ndarray:
    """Valeur moyenne de la moyenne des Z sur ``z_qubits``, pour chaque ligne de ``thetas``.

    Simulation par vecteur d'état d'un lot de jeux de paramètres. Les
    amplitudes ont la forme (B, 2, ..., 2), le qubit q étant sur l'axe n - q
    (convention little-endian de Qiskit).
    """
    n = ansatz.num_qubits
    index = {p: i for i, p in enumerate(ansatz.parameters)}
    states = np.zeros((len(thetas),) + (2,) * n, dtype=complex)
    states[(slice(None),) + (0,) * n] = 1

    for instruction in ansatz.data:
        op = instruction.operation
        if op.name == "barrier":
            continue
        qubits = [ansatz.find_bit(q).index for q in instruction.qubits]
        if op.is_parameterized():
            angle = op.params[0] if op.name in _ROTATIONS else None
            if not isinstance(angle, Parameter):
                raise ValueError(
                    f"Porte {op.name!r} non supportée : la règle du décalage de paramètre "
                    "suppose des rotations RX, RY ou RZ d'angle égal à un paramètre."
                )
            matrices = _rotation_matrices(op.name, thetas[:, index[angle]])
            states = _apply_batched_1q(states, matrices, n - qubits[0])
        else:
            matrix = Operator(op).data
            states = _apply_fixed(states, matrix, [n - q for q in reversed(qubits)])

    probs = np.abs(states) ** 2
    values = []
    for q in z_qubits:
        marginal = np.moveaxis(probs, n - q, 1).reshape(len(thetas), 2, -1).sum(axis=2)
        values.append(marginal[:, 0] - marginal[:, 1])
    return np.mean(values, axis=0)


def _cost_qubits(observable: str, n_qubits: int) -> list[int]:
    if observable == "Z0":
        return [0]
    if observable == "Zmean":
        return list(range(n_qubits))
    raise ValueError(f"Observable non supporté : {observable!r} (attendu : 'Z0' ou 'Zmean').")


def gradient_variance_details(
    ansatz: QuantumCircuit,
    n_samples: int = 200,
    observable: str = "Z0",
    seed: int | None = None,
) -> dict:
    """Calcule la variance du gradient de chaque paramètre d'un ansatz.

    On tire ``n_samples`` points uniformes dans [0, 2π] et, en chaque point,
    le gradient de chaque paramètre par la règle du décalage de paramètre :
    (f(θ + π/2) - f(θ - π/2)) / 2. La variance est prise sur les points,
    paramètre par paramètre.

    Observables de coût :

    - ``"Z0"`` (défaut) : ⟨Z⟩ sur le qubit 0, observable local ; seuls les
      paramètres dans le cône causal du qubit 0 ont un gradient non nul ;
    - ``"Zmean"`` : moyenne des ⟨Z⟩ sur tous les qubits, observable global
      au sens où chaque qubit contribue ; davantage de paramètres sont actifs.

    Un paramètre est inactif si la variance de son gradient est inférieure à
    1e-12 : par exemple un RZ appliqué à |0⟩, qui n'ajoute qu'une phase, ou
    un paramètre hors du cône causal de l'observable. La moyenne sur tous
    les paramètres (``mean_variance``) baisse mécaniquement quand la part de
    paramètres inactifs augmente (dilution) ; la moyenne sur les seuls
    paramètres actifs (``active_mean_variance``) isole le signal lié au
    plateau stérile.

    Limite : la règle du décalage n'est exacte que pour des rotations RX, RY
    ou RZ dont l'angle est un paramètre seul, chaque paramètre n'étant
    utilisé qu'une fois. Les autres portes paramétrées lèvent une
    ``ValueError`` ; un paramètre réutilisé donne un résultat faux.

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit paramétré à évaluer.
    n_samples : int
        Nombre de points tirés uniformément dans [0, 2π].
    observable : str
        ``"Z0"`` ou ``"Zmean"``.
    seed : int ou None
        Graine du générateur aléatoire, pour la reproductibilité.

    Retourne
    --------
    dict
        ``mean_variance`` (moyenne des variances sur tous les paramètres),
        ``active_mean_variance`` (moyenne sur les seuls paramètres actifs,
        variance >= 1e-12 ; ``nan`` s'il n'y en a aucun),
        ``variance_per_parameter`` (tableau, dans l'ordre de
        ``ansatz.parameters``), ``n_inactive_parameters`` et
        ``inactive_fraction``.

    Lève
    ----
    ValueError
        Si le circuit n'a aucun paramètre libre, si l'observable n'est pas
        supporté, ou si une porte paramétrée n'est pas une rotation simple.
    """
    n_params = ansatz.num_parameters
    if n_params == 0:
        raise ValueError("Le circuit n'a aucun paramètre libre.")
    z_qubits = _cost_qubits(observable, ansatz.num_qubits)

    rng = np.random.default_rng(seed)
    thetas = rng.uniform(0, 2 * np.pi, (n_samples, n_params))

    # Lignes 2p et 2p+1 : décalages +π/2 et -π/2 du paramètre p.
    shifts = np.zeros((2 * n_params, n_params))
    shifts[0::2][np.diag_indices(n_params)] = np.pi / 2
    shifts[1::2][np.diag_indices(n_params)] = -np.pi / 2

    chunk = max(1, _MAX_BATCH_AMPLITUDES // (2 * n_params * 2**ansatz.num_qubits))
    gradients = np.empty((n_samples, n_params))
    for start in range(0, n_samples, chunk):
        block = thetas[start : start + chunk]
        batch = (block[:, None, :] + shifts[None]).reshape(-1, n_params)
        costs = _expectations(ansatz, batch, z_qubits).reshape(len(block), 2 * n_params)
        gradients[start : start + chunk] = (costs[:, 0::2] - costs[:, 1::2]) / 2

    variances = gradients.var(axis=0)
    active = variances >= INACTIVE_THRESHOLD
    n_inactive = int(np.sum(~active))
    return {
        "mean_variance": float(variances.mean()),
        "active_mean_variance": float(variances[active].mean()) if active.any() else float("nan"),
        "variance_per_parameter": variances,
        "n_inactive_parameters": n_inactive,
        "inactive_fraction": n_inactive / n_params,
    }


def gradient_variance(
    ansatz: QuantumCircuit,
    n_samples: int = 200,
    observable: str = "Z0",
    seed: int | None = None,
) -> float:
    """Calcule la variance du gradient, moyennée sur tous les paramètres.

    Sert à détecter les plateaux stériles : une variance qui s'effondre quand
    le nombre de qubits augmente signale un paysage de coût plat. La
    variance est calculée pour chaque paramètre (règle du décalage de
    paramètre) puis moyennée : on évite ainsi le biais d'une mesure sur le
    seul premier paramètre, qui peut être sans effet sur le coût (RZ appliqué
    à |0⟩, paramètre hors du cône causal de l'observable). Les paramètres
    inactifs comptent dans la moyenne avec une variance nulle ; leur nombre
    est donné par ``gradient_variance_details``, qui documente aussi les
    observables ``"Z0"`` et ``"Zmean"`` et les limites de la méthode.

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit paramétré à évaluer.
    n_samples : int
        Nombre de points tirés uniformément dans [0, 2π].
    observable : str
        ``"Z0"`` (⟨Z⟩ sur le qubit 0) ou ``"Zmean"`` (moyenne des ⟨Z⟩).
    seed : int ou None
        Graine du générateur aléatoire, pour la reproductibilité.

    Retourne
    --------
    float
        Moyenne, sur tous les paramètres, de la variance empirique du gradient.

    Lève
    ----
    ValueError
        Si le circuit n'a aucun paramètre libre, si l'observable n'est pas
        supporté, ou si une porte paramétrée n'est pas une rotation simple.
    """
    return gradient_variance_details(
        ansatz, n_samples=n_samples, observable=observable, seed=seed
    )["mean_variance"]
