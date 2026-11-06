import pytest

from stochastiq import build_ansatz, hardware_cost, list_topologies


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
