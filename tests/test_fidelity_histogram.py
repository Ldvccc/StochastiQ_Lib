import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit.library import real_amplitudes

from stochastiq import build_ansatz, expressibility, fidelity_histogram


def test_probabilites_de_somme_1():
    hist = fidelity_histogram(real_amplitudes(3, reps=2), n_samples=200, n_bins=30, seed=0)
    assert len(hist["edges"]) == 31
    assert len(hist["circuit"]) == len(hist["haar"]) == 30
    assert hist["circuit"].sum() == pytest.approx(1)
    assert hist["haar"].sum() == pytest.approx(1)


def test_coherent_avec_expressibility():
    ansatz = real_amplitudes(3, reps=2)
    hist = fidelity_histogram(ansatz, n_samples=200, seed=0)
    p, q = hist["circuit"], hist["haar"]
    kl = np.sum(p * np.log((p + 1e-12) / (q + 1e-12)))
    assert expressibility(ansatz, n_samples=200, seed=0) == pytest.approx(kl, rel=1e-12)


@pytest.mark.parametrize(
    "ansatz, kwargs, expected",
    [
        # Valeurs obtenues avec l'implémentation d'avant le refactor.
        (real_amplitudes(3, reps=2), {"n_samples": 200, "seed": 0}, 0.4108859559616048),
        (build_ansatz("ryrz_linear", 2, 1), {"n_samples": 150, "n_bins": 20, "seed": 7}, 0.08902782302132872),
    ],
)
def test_expressibility_inchangee(ansatz, kwargs, expected):
    assert expressibility(ansatz, **kwargs) == pytest.approx(expected, rel=1e-12)


def test_circuit_sans_parametre():
    qc = QuantumCircuit(2)
    qc.h(0)
    with pytest.raises(ValueError):
        fidelity_histogram(qc)
