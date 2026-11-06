import pytest

from stochastiq import build_ansatz, entangling_capability, list_ansatz

NAMES = [
    "basic_entangler",
    "strongly_entangling",
    "hardware_efficient",
    "rotation_only",
    "all_to_all",
    "brick_wall",
    "data_reuploading",
]

# n = 4 qubits, L = 3 couches : (paramètres, CNOT)
EXPECTED = {
    "basic_entangler": (12, 12),
    "strongly_entangling": (36, 12),
    "hardware_efficient": (24, 9),
    "rotation_only": (12, 0),
    "all_to_all": (36, 18),
    "brick_wall": (24, 5),
    "data_reuploading": (36, 12),
}


def test_list_ansatz():
    assert list_ansatz() == NAMES


@pytest.mark.parametrize("name", NAMES)
def test_parametres_et_cnot(name):
    qc = build_ansatz(name, 4, 3)
    n_params, n_cx = EXPECTED[name]
    assert qc.num_parameters == n_params
    assert qc.count_ops().get("cx", 0) == n_cx


@pytest.mark.parametrize(
    "name, n_qubits, n_cx",
    [
        ("basic_entangler", 2, 1),
        ("basic_entangler", 1, 0),
        ("strongly_entangling", 2, 2),
        ("strongly_entangling", 1, 0),
        ("data_reuploading", 2, 2),
        ("data_reuploading", 1, 0),
    ],
)
def test_cas_limites_petits_circuits(name, n_qubits, n_cx):
    assert build_ansatz(name, n_qubits, 1).count_ops().get("cx", 0) == n_cx


def test_ordre_des_parametres():
    qc = build_ansatz("strongly_entangling", 3, 2)
    # Couche 1, qubit 2, rotation 1 (RY) : indice ((1 * 3) + 2) * 3 + 1 = 16.
    ry = [inst for inst in qc.data if inst.operation.name == "ry"]
    last = ry[-1]
    assert qc.find_bit(last.qubits[0]).index == 2
    assert last.operation.params[0].index == 16


def test_strongly_entangling_portee_des_cnot():
    qc = build_ansatz("strongly_entangling", 4, 3)
    pairs = [
        tuple(qc.find_bit(q).index for q in inst.qubits)
        for inst in qc.data
        if inst.operation.name == "cx"
    ]
    ring = lambda r: [(i, (i + r) % 4) for i in range(4)]
    assert pairs == ring(1) + ring(2) + ring(3)


def test_brick_wall_alterne():
    qc = build_ansatz("brick_wall", 5, 2)
    pairs = [
        tuple(qc.find_bit(q).index for q in inst.qubits)
        for inst in qc.data
        if inst.operation.name == "cx"
    ]
    assert pairs == [(0, 1), (2, 3), (1, 2), (3, 4)]


def test_rotation_only_sans_intrication():
    value = entangling_capability(build_ansatz("rotation_only", 3, 2), n_samples=50, seed=0)
    assert value == pytest.approx(0, abs=1e-9)


def test_nom_inconnu():
    with pytest.raises(ValueError) as error:
        build_ansatz("ry_linear", 4, 3)
    for name in NAMES:
        assert name in str(error.value)
