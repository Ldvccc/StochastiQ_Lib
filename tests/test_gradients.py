import pytest
from qiskit import QuantumCircuit

from stochastiq import build_ansatz, gradient_variance


def test_variance_positive():
    assert gradient_variance(build_ansatz("hardware_efficient", 3, 2), n_samples=50, seed=0) > 0


def test_meme_seed_meme_resultat():
    qc = build_ansatz("basic_entangler", 3, 2)
    a = gradient_variance(qc, n_samples=30, seed=3)
    b = gradient_variance(qc, n_samples=30, seed=3)
    assert a == b


def test_circuit_sans_parametre():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    with pytest.raises(ValueError):
        gradient_variance(qc)


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_variance_diminue_avec_le_nombre_de_qubits(seed):
    variances = [
        gradient_variance(build_ansatz("hardware_efficient", n, 10), n_samples=100, seed=seed)
        for n in (2, 3, 4)
    ]
    assert variances[0] > variances[1] > variances[2]
