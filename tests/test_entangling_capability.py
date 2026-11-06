import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import Statevector

from stochastiq import build_ansatz, entangling_capability
from stochastiq.metrics import _meyer_wallach


def test_meyer_wallach_etat_produit():
    state = Statevector.from_label("00")
    assert _meyer_wallach(state, 2) == pytest.approx(0)


def test_meyer_wallach_bell():
    state = np.array([1, 0, 0, 1]) / np.sqrt(2)
    assert _meyer_wallach(state, 2) == pytest.approx(1)


def test_meyer_wallach_ghz():
    state = np.zeros(8)
    state[0] = state[7] = 1 / np.sqrt(2)
    assert _meyer_wallach(state, 3) == pytest.approx(1)


def test_sans_cnot_pas_d_intrication():
    theta = ParameterVector("θ", 6)
    qc = QuantumCircuit(3)
    for layer in range(2):
        for q in range(3):
            qc.ry(theta[3 * layer + q], q)
    assert entangling_capability(qc, n_samples=50, seed=0) == pytest.approx(0, abs=1e-9)


def test_all_to_all_intrique():
    value = entangling_capability(build_ansatz("all_to_all", 3, 2), n_samples=100, seed=0)
    assert 0.2 < value <= 1


def test_meme_seed_meme_resultat():
    qc = build_ansatz("hardware_efficient", 3, 2)
    a = entangling_capability(qc, n_samples=50, seed=1)
    b = entangling_capability(qc, n_samples=50, seed=1)
    assert a == b


def test_circuit_sans_parametre():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    with pytest.raises(ValueError):
        entangling_capability(qc)
