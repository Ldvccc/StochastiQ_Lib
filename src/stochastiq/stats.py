from qiskit import QuantumCircuit, transpile

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
