import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.quantum_info import SparsePauliOp, Statevector

from stochastiq import build_ansatz, gradient_variance, gradient_variance_details


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


@pytest.mark.parametrize("name", ["data_reuploading", "strongly_entangling", "basic_entangler"])
def test_premier_parametre_inactif_n_annule_plus_la_moyenne(name):
    details = gradient_variance_details(build_ansatz(name, 4, 3), n_samples=200, seed=0)
    assert details["mean_variance"] > 1e-3
    assert details["n_inactive_parameters"] > 0
    # Le premier paramètre, seul mesuré auparavant, a un gradient identiquement nul.
    assert details["variance_per_parameter"][0] < 1e-12


def test_hardware_efficient_moyenne_non_nulle():
    assert gradient_variance(build_ansatz("hardware_efficient", 4, 3), n_samples=200, seed=0) > 1e-3


def test_details_coherents():
    qc = build_ansatz("brick_wall", 3, 2)
    details = gradient_variance_details(qc, n_samples=50, seed=4)
    variances = details["variance_per_parameter"]
    assert variances.shape == (qc.num_parameters,)
    assert details["mean_variance"] == pytest.approx(variances.mean())
    assert details["n_inactive_parameters"] == int((variances < 1e-12).sum())
    assert details["inactive_fraction"] == details["n_inactive_parameters"] / qc.num_parameters
    assert gradient_variance(qc, n_samples=50, seed=4) == details["mean_variance"]


@pytest.mark.parametrize("observable", ["Z0", "Zmean"])
def test_concorde_avec_statevector(observable):
    qc = build_ansatz("all_to_all", 3, 2)
    n = qc.num_qubits
    qubits = [0] if observable == "Z0" else range(n)
    op = SparsePauliOp.from_sparse_list([("Z", [q], 1 / len(qubits)) for q in qubits], n)

    def cost(theta):
        return Statevector(qc.assign_parameters(theta)).expectation_value(op).real

    rng = np.random.default_rng(5)
    thetas = rng.uniform(0, 2 * np.pi, (20, qc.num_parameters))
    gradients = np.empty_like(thetas)
    for i, theta in enumerate(thetas):
        for p in range(qc.num_parameters):
            shift = np.zeros(qc.num_parameters)
            shift[p] = np.pi / 2
            gradients[i, p] = (cost(theta + shift) - cost(theta - shift)) / 2
    details = gradient_variance_details(qc, n_samples=20, observable=observable, seed=5)
    np.testing.assert_allclose(details["variance_per_parameter"], gradients.var(axis=0), atol=1e-12)


def test_zmean_active_plus_de_parametres_que_z0():
    qc = build_ansatz("rotation_only", 3, 2)
    assert gradient_variance_details(qc, n_samples=50, observable="Z0", seed=0)["n_inactive_parameters"] == 4
    assert gradient_variance_details(qc, n_samples=50, observable="Zmean", seed=0)["n_inactive_parameters"] == 0


def test_observable_inconnu():
    with pytest.raises(ValueError, match="Zmean"):
        gradient_variance(build_ansatz("hardware_efficient", 2, 1), observable="Z1")


def test_porte_non_supportee():
    theta = Parameter("t")
    qc = QuantumCircuit(1)
    qc.rx(2 * theta, 0)
    with pytest.raises(ValueError, match="non supportée"):
        gradient_variance(qc, n_samples=5)
