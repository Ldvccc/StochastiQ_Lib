import pytest

from stochastiq import build_ansatz, circuit_stats, hardware_cost, list_topologies


def test_ring_ne_rajoute_aucun_cnot():
    cost = hardware_cost(build_ansatz("ry_circular", 4, 2), topology="ring", seed=0)
    assert cost["topology"] == "ring"
    assert cost["n_two_qubit_gates_after"] == cost["n_two_qubit_gates_before"]
    assert cost["overhead_two_qubit"] == 1


def test_line_rajoute_des_cnot():
    cost = hardware_cost(build_ansatz("ry_circular", 4, 2), topology="line", seed=0)
    assert cost["n_two_qubit_gates_after"] > cost["n_two_qubit_gates_before"]
    assert cost["overhead_two_qubit"] > 1


def test_trop_de_qubits():
    with pytest.raises(ValueError):
        hardware_cost(build_ansatz("ry_linear", 20, 1), topology="heavy_hex")


def test_topologie_inconnue():
    with pytest.raises(ValueError):
        hardware_cost(build_ansatz("ry_linear", 2, 1), topology="inconnue")


def test_list_topologies():
    assert list_topologies() == ["line", "ring", "full", "heavy_hex"]


def test_before_est_le_circuit_d_origine():
    qc = build_ansatz("ry_linear", 4, 3)
    cost = hardware_cost(qc, topology="line", seed=0)
    stats = circuit_stats(qc)
    assert cost["depth_before"] == cost["before"]["depth"] == stats["depth"]
    assert cost["n_two_qubit_gates_before"] == stats["n_two_qubit_gates"]
    assert cost["routing_overhead_two_qubit"] == 1.0


def test_routage_sur_ligne_d_un_circuit_circulaire():
    cost = hardware_cost(build_ansatz("ry_circular", 4, 3), topology="line", seed=0)
    assert cost["routing_overhead_two_qubit"] > 1
    assert cost["after"]["n_two_qubit_gates"] > cost["basis_only"]["n_two_qubit_gates"]


def test_sans_porte_a_2_qubits():
    with pytest.raises(ValueError, match="routage"):
        hardware_cost(build_ansatz("ry_linear", 1, 2), topology="line")
