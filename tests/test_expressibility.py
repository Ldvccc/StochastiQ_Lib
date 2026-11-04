import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import real_amplitudes

from stochastiq import expressibility


def test_plus_de_couches_plus_expressif():
    shallow = expressibility(real_amplitudes(3, reps=1), n_samples=800, seed=0)
    deep = expressibility(real_amplitudes(3, reps=4), n_samples=800, seed=0)
    assert deep < shallow


def test_meme_seed_meme_resultat():
    ansatz = real_amplitudes(3, reps=2)
    a = expressibility(ansatz, n_samples=200, seed=42)
    b = expressibility(ansatz, n_samples=200, seed=42)
    assert a == b


def test_circuit_sans_parametre():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    with pytest.raises(ValueError):
        expressibility(qc)
