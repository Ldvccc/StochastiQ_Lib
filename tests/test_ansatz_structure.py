from collections import Counter

import pytest

from stochastiq import ansatz_structure, build_ansatz, circuit_stats, list_ansatz

QISKIT_NAMES = {"RX": "rx", "RY": "ry", "RZ": "rz", "CNOT": "cx"}


@pytest.mark.parametrize("name", list_ansatz())
@pytest.mark.parametrize("n_qubits, layers", [(2, 1), (4, 3)])
def test_comptes_identiques_a_circuit_stats(name, n_qubits, layers):
    structure = ansatz_structure(name, n_qubits, layers)
    assert structure["n_qubits"] == n_qubits
    assert structure["layers"] == layers
    counts = Counter(
        QISKIT_NAMES[gate["type"]] for column in structure["columns"] for gate in column["gates"]
    )
    assert dict(counts) == circuit_stats(build_ansatz(name, n_qubits, layers))["gate_counts"]


@pytest.mark.parametrize("name", list_ansatz())
def test_indices_de_parametres_complets(name):
    structure = ansatz_structure(name, 3, 2)
    indices = sorted(
        gate["param_index"]
        for column in structure["columns"]
        for gate in column["gates"]
        if gate["param_index"] is not None
    )
    assert indices == list(range(build_ansatz(name, 3, 2).num_parameters))


def test_ordre_des_colonnes_hardware_efficient():
    columns = ansatz_structure("hardware_efficient", 3, 1)["columns"]
    # RY sur tous les qubits, RZ sur tous les qubits, puis un CNOT par colonne.
    assert [column["gates"][0]["type"] for column in columns] == ["RY", "RZ", "CNOT", "CNOT"]
    assert columns[1]["gates"][2] == {"type": "RZ", "qubits": [2], "param_index": 5}
    assert columns[2]["gates"] == [{"type": "CNOT", "qubits": [0, 1], "param_index": None}]
    assert columns[3]["gates"] == [{"type": "CNOT", "qubits": [1, 2], "param_index": None}]


def test_nom_inconnu():
    with pytest.raises(ValueError, match="hardware_efficient"):
        ansatz_structure("inconnu", 2, 1)
