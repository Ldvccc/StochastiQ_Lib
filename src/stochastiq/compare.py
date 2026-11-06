import numpy as np
import pandas as pd
from qiskit import QuantumCircuit

from .gradients import gradient_variance_details
from .metrics import entangling_capability, expressibility
from .stats import circuit_stats

_METRICS = {
    "expressibility": expressibility,
    "entangling_capability": entangling_capability,
}


def _aggregate(row: dict, metric: str, values: list[float]) -> None:
    if len(values) == 1:
        row[metric] = values[0]
    else:
        row[metric] = float(np.mean(values))
        row[f"{metric}_std"] = float(np.std(values, ddof=1))


def compare(
    ansatz_dict: dict[str, QuantumCircuit],
    n_samples: int = 1000,
    seed: int | None = None,
    n_seeds: int = 1,
) -> pd.DataFrame:
    """Compare plusieurs ansatz sur leurs statistiques et métriques.

    Paramètres
    ----------
    ansatz_dict : dict[str, QuantumCircuit]
        Circuits à comparer, indexés par leur nom.
    n_samples : int
        Nombre d'échantillons utilisé pour chaque métrique.
    seed : int ou None
        Graine du générateur aléatoire, pour la reproductibilité.
    n_seeds : int
        Nombre de graines (seed, seed+1, ...) sur lesquelles répéter chaque
        métrique. Si ``seed`` vaut None, les répétitions sont sans graine.

    Retourne
    --------
    pandas.DataFrame
        Une ligne par circuit (index : nom), colonnes ``n_qubits``,
        ``n_parameters``, ``depth``, ``n_two_qubit_gates``, ``expressibility``,
        ``entangling_capability``, ``gradient_variance`` (variance du gradient
        moyennée sur tous les paramètres, coût ``"Z0"``),
        ``gradient_variance_active`` (moyennée sur les seuls paramètres
        actifs) et ``inactive_fraction`` (part des paramètres inactifs),
        triée par expressibilité croissante (plus expressif d'abord). Si
        ``n_seeds > 1``, les colonnes sont des moyennes sur les graines, et
        ``expressibility``, ``entangling_capability``, ``gradient_variance``
        et ``gradient_variance_active`` sont chacune suivies d'une colonne
        ``<nom>_std`` (écart-type).

    Lève
    ----
    ValueError
        Si ``n_seeds`` est inférieur à 1.
    """
    if n_seeds < 1:
        raise ValueError("n_seeds doit être supérieur ou égal à 1.")
    seeds = [None] * n_seeds if seed is None else [seed + i for i in range(n_seeds)]

    rows = {}
    for name, ansatz in ansatz_dict.items():
        stats = circuit_stats(ansatz)
        row = {
            "n_qubits": stats["n_qubits"],
            "n_parameters": stats["n_parameters"],
            "depth": stats["depth"],
            "n_two_qubit_gates": stats["n_two_qubit_gates"],
        }
        for metric, func in _METRICS.items():
            _aggregate(row, metric, [func(ansatz, n_samples=n_samples, seed=s) for s in seeds])
        details = [gradient_variance_details(ansatz, n_samples=n_samples, seed=s) for s in seeds]
        _aggregate(row, "gradient_variance", [d["mean_variance"] for d in details])
        _aggregate(row, "gradient_variance_active", [d["active_mean_variance"] for d in details])
        row["inactive_fraction"] = float(np.mean([d["inactive_fraction"] for d in details]))
        rows[name] = row
    df = pd.DataFrame.from_dict(rows, orient="index")
    return df.sort_values("expressibility")


def pareto_front(
    points: list[tuple[float, float]],
    minimize_x: bool = True,
    maximize_y: bool = True,
) -> list[bool]:
    """Indique, pour chaque point (x, y), s'il appartient au front de Pareto.

    Un point est dominé si un autre point est meilleur ou égal sur x et sur
    y, et strictement meilleur sur au moins l'un des deux. Les points
    identiques ne se dominent pas.

    Paramètres
    ----------
    points : liste de (x, y)
        Points à évaluer.
    minimize_x : bool
        True si un x plus petit est meilleur.
    maximize_y : bool
        True si un y plus grand est meilleur.

    Retourne
    --------
    list[bool]
        True pour chaque point non dominé, dans l'ordre de ``points``.
    """
    # On se ramène à deux critères à minimiser.
    costs = [
        (x if minimize_x else -x, -y if maximize_y else y) for x, y in points
    ]
    front = []
    for i, (xi, yi) in enumerate(costs):
        dominated = any(
            xj <= xi and yj <= yi and (xj < xi or yj < yi)
            for j, (xj, yj) in enumerate(costs)
            if j != i
        )
        front.append(not dominated)
    return front
