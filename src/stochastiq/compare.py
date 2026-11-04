import pandas as pd
from qiskit import QuantumCircuit

from .gradients import gradient_variance
from .metrics import entangling_capability, expressibility
from .stats import circuit_stats


def compare(
    ansatz_dict: dict[str, QuantumCircuit],
    n_samples: int = 1000,
    seed: int | None = None,
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

    Retourne
    --------
    pandas.DataFrame
        Une ligne par circuit (index : nom), colonnes ``n_qubits``,
        ``n_parameters``, ``depth``, ``n_two_qubit_gates``, ``expressibility``,
        ``entangling_capability`` et ``gradient_variance``, triée par
        expressibilité croissante (plus expressif d'abord).
    """
    rows = {}
    for name, ansatz in ansatz_dict.items():
        stats = circuit_stats(ansatz)
        rows[name] = {
            "n_qubits": stats["n_qubits"],
            "n_parameters": stats["n_parameters"],
            "depth": stats["depth"],
            "n_two_qubit_gates": stats["n_two_qubit_gates"],
            "expressibility": expressibility(ansatz, n_samples=n_samples, seed=seed),
            "entangling_capability": entangling_capability(
                ansatz, n_samples=n_samples, seed=seed
            ),
            "gradient_variance": gradient_variance(ansatz, n_samples=n_samples, seed=seed),
        }
    df = pd.DataFrame.from_dict(rows, orient="index")
    return df.sort_values("expressibility")
