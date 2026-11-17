from qiskit import QuantumCircuit, transpile

from .noise import transpiled_gate_counts

_BASIS_GATES = ["ry", "rz", "rx", "cx", "h"]


def circuit_stats(ansatz: QuantumCircuit) -> dict:
    """Retourne des statistiques structurelles d'un ansatz.

    Le circuit est d'abord transpilé vers les portes de base
    ``["ry", "rz", "rx", "cx", "h"]`` (niveau d'optimisation 0), pour que les
    circuits de la bibliothèque Qiskit donnent des chiffres cohérents.

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit à analyser.

    Retourne
    --------
    dict
        ``n_qubits``, ``n_parameters``, ``depth``, ``n_two_qubit_gates`` et
        ``gate_counts`` (dict nom de porte -> nombre).
    """
    qc = transpile(ansatz, basis_gates=_BASIS_GATES, optimization_level=0)
    gate_counts = {name: n for name, n in qc.count_ops().items() if name != "barrier"}
    n_two_qubit_gates = sum(
        1
        for instruction in qc.data
        if instruction.operation.num_qubits == 2 and instruction.operation.name != "barrier"
    )
    return {
        "n_qubits": qc.num_qubits,
        "n_parameters": qc.num_parameters,
        "depth": qc.depth(),
        "n_two_qubit_gates": n_two_qubit_gates,
        "gate_counts": gate_counts,
    }


def circuit_features(ansatz: QuantumCircuit) -> dict:
    """Caractéristiques numériques d'un circuit, pour la base de résultats et la prédiction.

    ``n_qubits``, ``n_parameters``, ``depth``, ``n_two_qubit_gates`` et
    ``n_one_qubit_gates`` (portes de ``circuit_stats``), puis ``line_n1``,
    ``line_n2`` et ``line_depth`` : le circuit transpilé sur une ligne comme
    pour le bruit (``transpiled_gate_counts``, graine 0).
    """
    stats = circuit_stats(ansatz)
    line = transpiled_gate_counts(ansatz, "line", seed=0)
    n_gates = sum(stats["gate_counts"].values())
    return {
        "n_qubits": stats["n_qubits"],
        "n_parameters": stats["n_parameters"],
        "depth": stats["depth"],
        "n_two_qubit_gates": stats["n_two_qubit_gates"],
        "n_one_qubit_gates": n_gates - stats["n_two_qubit_gates"],
        "line_n1": line["n1"],
        "line_n2": line["n2"],
        "line_depth": line["depth"],
    }
