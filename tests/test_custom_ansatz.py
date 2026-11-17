from collections import Counter

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter

from stochastiq import (
    ansatz_structure,
    build_ansatz,
    build_from_spec,
    circuit_stats,
    circuit_structure,
    gradient_scaling,
    load_qasm,
    spec_qubits,
    validate_ansatz,
    validate_spec,
)
from stochastiq.ansatz import ENTANGLERS, entangler_pairs

QASM3 = """OPENQASM 3.0;
include "stdgates.inc";
input float[64] a;
input float[64] b;
input float[64] c;
qubit[3] q;
ry(a) q[0];
ry(b) q[1];
rz(c) q[2];
cx q[0], q[1];
h q[2];
cx q[1], q[2];
"""

try:
    import qiskit_qasm3_import  # noqa: F401

    HAS_QASM3 = True
except ImportError:
    HAS_QASM3 = False

needs_qasm3 = pytest.mark.skipif(not HAS_QASM3, reason="option qasm3 absente")

# Spec équivalente à chaque ansatz du catalogue : mêmes portes, même ordre de paramètres.
EQUIVALENT = {
    "basic_entangler": {"rotations": ["rx"], "entangler": "basic_ring"},
    "strongly_entangling": {"rotations": ["rz", "ry", "rz"], "entangler": "strongly"},
    "hardware_efficient": {"rotations": ["ry", "rz"], "entangler": "linear"},
    "rotation_only": {"rotations": ["ry"], "entangler": "none"},
    "all_to_all": {"rotations": ["rx", "ry", "rz"], "entangler": "all_pairs"},
    "brick_wall": {"rotations": ["ry", "rz"], "entangler": "brick"},
    "data_reuploading": {"rotations": ["rz", "ry", "rz"], "entangler": "ring"},
}


@pytest.mark.parametrize("name", list(EQUIVALENT))
@pytest.mark.parametrize("n_qubits, layers", [(2, 1), (4, 3), (5, 2)])
def test_spec_identique_au_catalogue(name, n_qubits, layers):
    built = build_from_spec(EQUIVALENT[name], n_qubits, layers)
    reference = build_ansatz(name, n_qubits, layers)
    assert [(i.operation.name, [built.find_bit(q).index for q in i.qubits], str(i.operation.params)) for i in built.data] == [
        (i.operation.name, [reference.find_bit(q).index for q in i.qubits], str(i.operation.params)) for i in reference.data
    ]


def test_entangleurs_publics():
    assert set(ENTANGLERS) == {"ring", "basic_ring", "strongly", "linear", "all_pairs", "brick", "none"}
    assert entangler_pairs("brick", 5, 1) == [(1, 2), (3, 4)]
    with pytest.raises(ValueError, match="Motif d'intrication inconnu"):
        entangler_pairs("etoile", 3, 0)


def test_spec_custom_fixe_n():
    spec = {"rotations": ["ry"], "entangler": "custom", "pairs": [[0, 2], [2, 1]]}
    assert spec_qubits(spec) == 3
    qc = build_from_spec(spec, 3, 2)
    assert qc.num_parameters == 6
    assert Counter(i.operation.name for i in qc.data) == {"ry": 6, "cx": 4}
    with pytest.raises(ValueError, match="fixe 3 qubits"):
        build_from_spec(spec, 4, 1)
    assert spec_qubits({"rotations": ["rx"], "entangler": "ring"}) is None


@pytest.mark.parametrize(
    "spec, message",
    [
        ({"rotations": [], "entangler": "ring"}, "de 1 à 3 rotations"),
        ({"rotations": ["ry", "rz", "rx", "ry"], "entangler": "ring"}, "de 1 à 3 rotations"),
        ({"rotations": ["u3"], "entangler": "ring"}, "Rotation inconnue"),
        ({"rotations": ["ry"], "entangler": "etoile"}, "Motif d'intrication inconnu"),
        ({"rotations": ["ry"], "entangler": "ring", "pairs": [[0, 1]]}, "n'est permis qu'avec"),
        ({"rotations": ["ry"], "entangler": "custom"}, "demande « pairs »"),
        ({"rotations": ["ry"], "entangler": "custom", "pairs": [[0, 0]]}, "distincts"),
        ({"rotations": ["ry"], "entangler": "custom", "pairs": [[0, 9]]}, "fixent 10 qubits"),
        ({"rotations": ["ry"], "entangler": "custom", "pairs": [[0, True]]}, "CNOT invalide"),
        ({"rotations": ["ry"], "entangler": "ring", "code": "import os"}, "Clé(s) inconnue(s)"),
        ("ry", "objet JSON"),
    ],
)
def test_spec_invalide(spec, message):
    with pytest.raises(ValueError, match=message.replace("(", r"\(").replace(")", r"\)")):
        validate_spec(spec)


@needs_qasm3
def test_qasm3_charge_et_valide():
    qc = validate_ansatz(load_qasm(QASM3))
    assert qc.num_qubits == 3
    assert [p.name for p in qc.parameters] == ["a", "b", "c"]


def test_qasm2_sans_parametre_refuse():
    qc = load_qasm('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nry(0.3) q[0];\ncx q[0],q[1];\n')
    assert qc.num_parameters == 0
    with pytest.raises(ValueError, match="OpenQASM 2 ne permet pas de paramètres"):
        validate_ansatz(qc)


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "vide"),
        ("OPENQASM 2.0;\nqreg q[2];\nfoo q[0];\n", "Texte OpenQASM invalide"),
        ("x" * 20_001, "20000 caractères"),
    ],
)
def test_qasm_invalide(text, message):
    with pytest.raises(ValueError, match=message):
        load_qasm(text)


def _circuit(builder) -> QuantumCircuit:
    qc = QuantumCircuit(2)
    builder(qc, Parameter("a"), Parameter("b"))
    return qc


@pytest.mark.parametrize(
    "builder, message",
    [
        (lambda qc, a, b: (qc.ry(2 * a, 0), qc.rz(b, 1)), "porte n° 1 « ry »"),
        (lambda qc, a, b: (qc.ry(a, 0), qc.p(b, 1)), "porte n° 2 « p »"),
        (lambda qc, a, b: (qc.ry(a, 0), qc.ry(a, 1)), "utilisé\\(s\\) plusieurs fois : a"),
        (lambda qc, a, b: (qc.ry(a, 0), qc.rz(b, 1), qc.measure_all()), "« measure »"),
        (lambda qc, a, b: (qc.ry(a, 0), qc.rz(b, 1), qc.reset(0)), "« reset »"),
    ],
)
def test_validation_nomme_la_porte_fautive(builder, message):
    with pytest.raises(ValueError, match=message):
        validate_ansatz(_circuit(builder))


def test_validation_tailles():
    with pytest.raises(ValueError, match="de 2 à 8"):
        validate_ansatz(QuantumCircuit(9))
    big = QuantumCircuit(2)
    for i in range(301):
        big.ry(Parameter(f"p{i:03d}"), i % 2)
    with pytest.raises(ValueError, match="300 au plus"):
        validate_ansatz(big)
    deep = QuantumCircuit(2)
    deep.ry(Parameter("a"), 0)
    for _ in range(501):
        deep.x(1)
    with pytest.raises(ValueError, match="profondeur"):
        validate_ansatz(deep)
    assert validate_ansatz(build_ansatz("all_to_all", 8, 8)).num_parameters == 192


@pytest.mark.parametrize("name", list(EQUIVALENT))
def test_circuit_structure_comptes(name):
    qc = build_ansatz(name, 4, 2)
    structure = circuit_structure(qc)
    counts = Counter(g["type"].lower().replace("cnot", "cx") for c in structure["columns"] for g in c["gates"])
    assert dict(counts) == circuit_stats(qc)["gate_counts"]
    indices = sorted(g["param_index"] for c in structure["columns"] for g in c["gates"] if g["param_index"] is not None)
    assert indices == list(range(qc.num_parameters))


def test_circuit_structure_sans_chevauchement():
    qc = QuantumCircuit(3)
    qc.cx(0, 2)  # couvre les qubits 0 à 2
    qc.h(1)  # doit passer dans la colonne suivante
    qc.ry(Parameter("a"), 0)
    columns = circuit_structure(qc)["columns"]
    assert [[g["type"] for g in c["gates"]] for c in columns] == [["CNOT"], ["H", "RY"]]
    assert columns[1]["gates"][1]["param_index"] == 0


def test_ansatz_structure_inchange():
    structure = ansatz_structure("hardware_efficient", 3, 1)
    assert structure["layers"] == 1
    assert [c["gates"][0]["type"] for c in structure["columns"]] == ["RY", "RZ", "CNOT", "CNOT"]


def test_gradient_scaling_avec_un_constructeur():
    spec = EQUIVALENT["hardware_efficient"]
    by_name = gradient_scaling("hardware_efficient", range(2, 4), layers=2, n_samples=20, seed=0)
    by_builder = gradient_scaling(lambda n, layers: build_from_spec(spec, n, layers), range(2, 4), layers=2, n_samples=20, seed=0)
    assert by_name.equals(by_builder)
    assert np.isfinite(by_builder["mean_variance"]).all()
