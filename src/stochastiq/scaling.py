from collections.abc import Callable, Iterable

from qiskit import QuantumCircuit

import numpy as np
import pandas as pd

from .ansatz import build_ansatz
from .gradients import gradient_variance_details

_LAYERS_MODES = ("fixed", "linear")


def gradient_scaling(
    name: str | Callable[[int, int], QuantumCircuit],
    qubit_range: Iterable[int] = range(2, 9),
    layers: int = 3,
    layers_mode: str = "fixed",
    n_samples: int = 100,
    observable: str = "Z0",
    seed: int | None = None,
    callback: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    """Étudie la variance du gradient d'un ansatz en fonction du nombre de qubits.

    Pour chaque nombre de qubits n de ``qubit_range``, construit l'ansatz
    avec ``build_ansatz`` et calcule ``gradient_variance_details``. Une
    décroissance exponentielle de la variance avec n signale un plateau
    stérile (voir ``fit_decay``).

    Paramètres
    ----------
    name : str ou callable
        Nom de l'ansatz, parmi ``list_ansatz()``, ou constructeur
        ``(n_qubits, layers) -> QuantumCircuit`` (par exemple un ansatz du
        client construit par ``custom_ansatz.build_from_spec``).
    qubit_range : itérable d'entiers
        Nombres de qubits étudiés.
    layers : int
        Nombre de couches en mode ``"fixed"``.
    layers_mode : str
        ``"fixed"`` (toujours ``layers`` couches) ou ``"linear"`` (autant de
        couches que de qubits, pour étudier une profondeur croissante).
    n_samples : int
        Nombre de points tirés pour chaque nombre de qubits.
    observable : str
        ``"Z0"`` (local), ``"Zmean"`` ou ``"Zall"`` (global), voir
        ``gradient_variance_details``.
    seed : int ou None
        Graine du générateur aléatoire, la même pour chaque nombre de qubits.
    callback : callable ou None
        Appelée avec ``(done, total)`` après chaque nombre de qubits, par
        exemple pour une barre de progression.

    Retourne
    --------
    pandas.DataFrame
        Une ligne par nombre de qubits : ``n_qubits``, ``layers``,
        ``n_parameters``, ``mean_variance`` (tous les paramètres),
        ``active_mean_variance`` (paramètres actifs seulement) et
        ``inactive_fraction``.

    Lève
    ----
    ValueError
        Si ``layers_mode`` est inconnu, si ``qubit_range`` est vide ou si le
        nom d'ansatz est inconnu.
    """
    if layers_mode not in _LAYERS_MODES:
        raise ValueError(
            f"Mode de couches inconnu : {layers_mode!r} (attendu : 'fixed' ou 'linear')."
        )
    qubits = list(qubit_range)
    if not qubits:
        raise ValueError("qubit_range est vide.")

    rows = []
    for done, n_qubits in enumerate(qubits, start=1):
        n_layers = layers if layers_mode == "fixed" else n_qubits
        ansatz = build_ansatz(name, n_qubits, n_layers) if isinstance(name, str) else name(n_qubits, n_layers)
        details = gradient_variance_details(
            ansatz, n_samples=n_samples, observable=observable, seed=seed
        )
        rows.append(
            {
                "n_qubits": n_qubits,
                "layers": n_layers,
                "n_parameters": ansatz.num_parameters,
                "mean_variance": details["mean_variance"],
                "active_mean_variance": details["active_mean_variance"],
                "inactive_fraction": details["inactive_fraction"],
            }
        )
        if callback is not None:
            callback(done, len(qubits))
    return pd.DataFrame(rows)


def fit_decay(n_qubits: Iterable[float], variances: Iterable[float]) -> dict:
    """Ajuste une décroissance exponentielle de la variance en fonction de n.

    Régression linéaire de log(variance) sur n ; les variances nulles ou
    négatives sont ignorées. Le facteur par qubit est exp(pente) : la
    variance est multipliée par ce facteur à chaque qubit ajouté.

    Paramètres
    ----------
    n_qubits : itérable de nombres
        Nombres de qubits.
    variances : itérable de nombres
        Variances correspondantes.

    Retourne
    --------
    dict
        ``factor_per_qubit`` (None si moins de 3 points valides), ``r2``
        (coefficient de détermination de la régression, None dans le même
        cas) et ``n_points`` (nombre de points valides).
    """
    n = np.asarray(list(n_qubits), dtype=float)
    v = np.asarray(list(variances), dtype=float)
    valid = v > 0
    n, log_v = n[valid], np.log(v[valid])
    if len(n) < 3:
        return {"factor_per_qubit": None, "r2": None, "n_points": int(len(n))}

    slope, intercept = np.polyfit(n, log_v, 1)
    residuals = log_v - (slope * n + intercept)
    ss_tot = np.sum((log_v - log_v.mean()) ** 2)
    r2 = 1.0 if ss_tot == 0 else float(1 - np.sum(residuals**2) / ss_tot)
    return {"factor_per_qubit": float(np.exp(slope)), "r2": r2, "n_points": int(len(n))}
