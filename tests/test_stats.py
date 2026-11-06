import pytest
from qiskit.circuit.library import real_amplitudes

from stochastiq import build_ansatz, circuit_stats


def test_hardware_efficient():
    stats = circuit_stats(build_ansatz("hardware_efficient", 4, 3))
    assert stats["n_qubits"] == 4
    assert stats["n_parameters"] == 24
    assert stats["n_two_qubit_gates"] == 9
    assert stats["gate_counts"] == {"ry": 12, "rz": 12, "cx": 9}


@pytest.mark.parametrize("name, n_cx", [("data_reuploading", 12), ("all_to_all", 18)])
def test_nombre_de_cnot(name, n_cx):
    stats = circuit_stats(build_ansatz(name, 4, 3))
    assert stats["n_two_qubit_gates"] == n_cx


def test_circuit_bibliotheque_qiskit():
    stats = circuit_stats(real_amplitudes(4, reps=3))
    assert stats["n_parameters"] == 16
    assert stats["gate_counts"]["ry"] == 16
    assert stats["n_two_qubit_gates"] == 9
