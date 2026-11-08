import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from stochastiq import build_ansatz, uniform
from stochastiq.baselines import chow_liu_baseline, chow_liu_tree, classical_baselines, independent_baseline
from stochastiq.gradients import batched_probabilities
from stochastiq.training import distribution_metrics, hellinger, loss_and_gradient, loss_value, mmd_kernel, train_qcbm

TARGET_2Q = np.array([0.4, 0.1, 0.1, 0.4])


def test_probabilites_en_lot_identiques_a_statevector():
    qc = build_ansatz("strongly_entangling", 3, 2)
    thetas = np.random.default_rng(1).uniform(0, 2 * np.pi, (5, qc.num_parameters))
    expected = [Statevector(qc.assign_parameters(t)).probabilities() for t in thetas]
    np.testing.assert_allclose(batched_probabilities(qc, thetas), expected, atol=1e-12)


@pytest.mark.parametrize("loss", ["kl", "mmd"])
def test_gradient_identique_aux_differences_finies(loss):
    qc = build_ansatz("hardware_efficient", 3, 1)
    target = np.random.default_rng(2).dirichlet(np.ones(8))
    theta = np.random.default_rng(3).uniform(0, 2 * np.pi, qc.num_parameters)
    kernel = mmd_kernel(3) if loss == "mmd" else None
    _, gradient = loss_and_gradient(qc, target, theta, loss, kernel)

    def f(x):
        return loss_value(loss, batched_probabilities(qc, x)[0], target, kernel)

    step = 1e-6
    finite = [(f(theta + step * e) - f(theta - step * e)) / (2 * step) for e in np.eye(theta.size)]
    np.testing.assert_allclose(gradient, finite, atol=1e-6)


@pytest.mark.parametrize(
    "loss, optimizer, learning_rate, max_iter",
    [("kl", "adam", 0.1, 200), ("mmd", "adam", 0.1, 200), ("tvd", "spsa", 0.5, 300), ("tvd", "cobyla", 0.5, 200)],
)
def test_apprentissage_d_une_cible_a_2_qubits(loss, optimizer, learning_rate, max_iter):
    result = train_qcbm(
        build_ansatz("hardware_efficient", 2, 2), TARGET_2Q, loss=loss, optimizer=optimizer,
        learning_rate=learning_rate, max_iter=max_iter, seed=0,
    )
    assert result["metrics"]["tvd"] < 0.05
    assert sum(result["probabilities"]) == pytest.approx(1)
    assert 1 <= result["n_iterations"] <= max_iter
    assert len(result["history"]) == result["n_iterations"]
    assert result["n_parameters"] == 8


def test_la_perte_diminue_avec_adam():
    history = train_qcbm(build_ansatz("hardware_efficient", 2, 2), TARGET_2Q, max_iter=100, seed=0)["history"]
    assert history[-1] < history[0]


@pytest.mark.parametrize("shots", [None, 500])
def test_reproductible_avec_la_graine(shots):
    qc = build_ansatz("hardware_efficient", 2, 2)
    a = train_qcbm(qc, TARGET_2Q, max_iter=30, seed=4, shots=shots)
    b = train_qcbm(qc, TARGET_2Q, max_iter=30, seed=4, shots=shots)
    assert a["history"] == b["history"]
    assert a["params"] == b["params"]
    c = train_qcbm(qc, TARGET_2Q, max_iter=30, seed=5, shots=shots)
    assert c["params"] != a["params"]


def test_tirages_metriques_finales_exactes():
    qc = build_ansatz("hardware_efficient", 2, 2)
    result = train_qcbm(qc, TARGET_2Q, max_iter=50, seed=0, shots=200)
    exact = batched_probabilities(qc, np.array(result["params"]))[0]
    assert result["probabilities"] == pytest.approx(exact.tolist())
    assert result["metrics"] == pytest.approx(distribution_metrics(TARGET_2Q, exact))


def test_refus():
    qc = build_ansatz("hardware_efficient", 2, 1)
    with pytest.raises(ValueError, match="SPSA ou COBYLA"):
        train_qcbm(qc, TARGET_2Q, loss="tvd", optimizer="adam")
    with pytest.raises(ValueError, match="Perte inconnue"):
        train_qcbm(qc, TARGET_2Q, loss="js")
    with pytest.raises(ValueError, match="Optimiseur inconnu"):
        train_qcbm(qc, TARGET_2Q, optimizer="lbfgs")
    with pytest.raises(ValueError, match="8 états"):
        train_qcbm(qc, uniform(3))
    with pytest.raises(ValueError, match="somme"):
        train_qcbm(qc, [0.5, 0.5, 0.5, 0.5])


def test_metriques():
    p, q = np.array([0.5, 0.5, 0, 0]), np.array([0.25, 0.25, 0.25, 0.25])
    metrics = distribution_metrics(p, q)
    assert metrics["tvd"] == pytest.approx(0.5)
    assert metrics["kl"] == pytest.approx(np.log(2))
    assert metrics["hellinger"] == pytest.approx(np.sqrt(1 - np.sqrt(0.5)))
    assert hellinger(p, p) == pytest.approx(0, abs=1e-7)


def test_references_exactes_sur_une_distribution_produit():
    marginals = [0.2, 0.7, 0.5]  # P(bit q = 1)
    states = np.arange(8)
    bits = (states[:, None] >> np.arange(3)) & 1
    product = np.prod(np.where(bits == 1, marginals, 1 - np.array(marginals)), axis=1)
    for result in classical_baselines(product).values():
        assert result["metrics"]["tvd"] == pytest.approx(0, abs=1e-12)
        assert result["probabilities"] == pytest.approx(product.tolist())
    assert independent_baseline(product)["n_parameters"] == 3
    assert chow_liu_baseline(product)["n_parameters"] == 5


def test_chow_liu_exact_sur_un_arbre_mais_pas_les_marginales():
    # Chaîne de Markov x0 -> x1 -> x2 (copie bruitée), structure d'arbre.
    probs = np.zeros(8)
    for x0 in (0, 1):
        for x1 in (0, 1):
            for x2 in (0, 1):
                p1 = 0.9 if x1 == x0 else 0.1
                p2 = 0.8 if x2 == x1 else 0.2
                probs[x0 | (x1 << 1) | (x2 << 2)] = 0.5 * p1 * p2
    assert chow_liu_tree(probs) == [(0, 1), (1, 2)]
    assert chow_liu_baseline(probs)["metrics"]["tvd"] == pytest.approx(0, abs=1e-12)
    assert independent_baseline(probs)["metrics"]["tvd"] > 0.1
