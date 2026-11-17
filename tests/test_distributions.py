import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from stochastiq import (
    bars_and_stripes,
    bimodal,
    from_probabilities,
    from_samples,
    gaussian,
    ising_boltzmann,
    list_distributions,
    lognormal,
    problem_features,
    reference_distribution,
    uniform,
)
from stochastiq.distributions import bitstring, check_probabilities


@pytest.mark.parametrize("name", list_distributions())
@pytest.mark.parametrize("n_qubits", [2, 4, 6, 8])
def test_vecteurs_de_probabilites(name, n_qubits):
    if name == "bars_and_stripes" and n_qubits not in (4, 6):
        with pytest.raises(ValueError, match="Bars-and-Stripes"):
            reference_distribution(name, n_qubits)
        return
    probs = reference_distribution(name, n_qubits, seed=0)
    assert probs.shape == (2**n_qubits,)
    assert probs.min() >= 0
    assert probs.sum() == pytest.approx(1)


@pytest.mark.parametrize("n_qubits", [1, 9, 3.5])
def test_nombre_de_qubits_borne(n_qubits):
    with pytest.raises(ValueError, match="de 2 à 8"):
        uniform(n_qubits)


def test_formes_attendues():
    g = gaussian(4)
    assert g[7] == pytest.approx(g[8]) and g.argmax() in (7, 8)  # symétrique autour de 7,5
    b = bimodal(5)
    assert b[8] > b[16] < b[24]  # creux entre les deux modes
    ln = lognormal(5)
    assert 0 < ln.argmax() < 16  # mode à gauche, queue à droite
    assert uniform(3) == pytest.approx(np.full(8, 1 / 8))


def test_bars_and_stripes():
    two_by_two = bars_and_stripes(4)
    assert np.count_nonzero(two_by_two) == 6
    # Barre du haut allumée : pixels (0,0) et (0,1), soit les qubits 0 et 1, donc l'indice 3.
    assert two_by_two[0b0011] == pytest.approx(1 / 6)
    assert two_by_two[0b0110] == 0  # diagonale : ni barre ni rayure
    assert np.count_nonzero(bars_and_stripes(6)) == 10


def test_ising_reproductible_et_dependant_de_la_graine():
    assert ising_boltzmann(4, seed=3) == pytest.approx(ising_boltzmann(4, seed=3))
    assert not np.allclose(ising_boltzmann(4, seed=3), ising_boltzmann(4, seed=4))
    # Sans champ local, l'énergie est invariante par retournement de tous les spins.
    p = ising_boltzmann(4, seed=1)
    assert p == pytest.approx(p[::-1])
    assert ising_boltzmann(3, beta=0) == pytest.approx(uniform(3))


def test_distribution_inconnue():
    with pytest.raises(ValueError, match="gaussian"):
        reference_distribution("poisson", 3)


def test_ordre_des_bits_little_endian_comme_qiskit():
    probs = from_probabilities({"01": 1.0})
    assert probs[1] == 1.0  # qubit 0 à 1
    qc = QuantumCircuit(2)
    qc.x(0)
    assert Statevector(qc).probabilities() == pytest.approx(probs)
    assert bitstring(1, 2) == "01"
    assert bitstring(6, 3) == "110"


def test_from_probabilities_strict():
    assert from_probabilities({"00": 0.25, "11": 0.75}) == pytest.approx([0.25, 0, 0, 0.75])
    with pytest.raises(ValueError, match="négative"):
        from_probabilities({"00": 1.1, "11": -0.1})
    with pytest.raises(ValueError, match="somme"):
        from_probabilities({"00": 0.5, "11": 0.49})
    from_probabilities({"00": 0.5, "11": 0.5 + 5e-7})  # dans la tolérance de 1e-6
    with pytest.raises(ValueError, match="même longueur"):
        from_probabilities({"00": 0.5, "111": 0.5})
    with pytest.raises(ValueError, match="invalide"):
        from_probabilities({"0a": 1.0})
    with pytest.raises(ValueError, match="de 2 à 8"):
        from_probabilities({"0": 1.0})


def test_from_samples_une_variable():
    probs = from_samples([0.0, 0.1, 0.3, 0.99, 1.0], n_qubits=2, ranges=[(0, 1)])
    # Classes [0, 0,25[, [0,25, 0,5[, [0,5, 0,75[, [0,75, 1] ; la borne 1 va dans la dernière.
    assert probs == pytest.approx([2 / 5, 1 / 5, 0, 2 / 5])


def test_from_samples_deux_variables_et_gray():
    samples = [[0.0, 3.0], [0.0, 3.0], [9.9, 0.0]]
    binary = from_samples(samples, n_qubits=4, ranges=[(0, 10), (0, 4)])
    # Variable 1 sur les qubits 0-1, variable 2 sur les qubits 2-3.
    assert binary[0 | (3 << 2)] == pytest.approx(2 / 3)
    assert binary[3 | (0 << 2)] == pytest.approx(1 / 3)
    gray = from_samples(samples, n_qubits=4, ranges=[(0, 10), (0, 4)], encoding="gray")
    assert gray[0 | (2 << 2)] == pytest.approx(2 / 3)  # classe 3 -> code de Gray 2
    assert gray[2 | (0 << 2)] == pytest.approx(1 / 3)


def test_from_samples_refus():
    with pytest.raises(ValueError, match="ne se répartissent pas"):
        from_samples([[0, 0]], n_qubits=3, ranges=[(0, 1), (0, 1)])
    with pytest.raises(ValueError, match="sortent de l'intervalle"):
        from_samples([1.5], n_qubits=2, ranges=[(0, 1)])
    with pytest.raises(ValueError, match="Intervalle vide"):
        from_samples([0.0], n_qubits=2, ranges=[(1, 1)])
    with pytest.raises(ValueError, match="intervalle"):
        from_samples([[0, 0]], n_qubits=2, ranges=[(0, 1)])
    with pytest.raises(ValueError, match="Encodage"):
        from_samples([0.5], n_qubits=2, ranges=[(0, 1)], encoding="unaire")


def test_caracteristiques():
    f = problem_features(uniform(3))
    assert f == pytest.approx(
        {"n_qubits": 3, "entropy": 1.0, "support_fraction": 1.0, "max_probability": 1 / 8, "mean_mutual_information": 0.0}
    )
    correlated = problem_features(from_probabilities({"00": 0.5, "11": 0.5}))
    assert correlated["mean_mutual_information"] == pytest.approx(1.0)
    assert correlated["entropy"] == pytest.approx(0.5)
    assert correlated["support_fraction"] == pytest.approx(0.5)
    # Distribution produit : bits indépendants, information mutuelle nulle.
    p0, p1 = np.array([0.8, 0.2]), np.array([0.3, 0.7])
    product = np.kron(p1, p0)  # qubit 0 = bit de poids faible
    assert problem_features(product)["mean_mutual_information"] == pytest.approx(0.0, abs=1e-12)


def test_information_mutuelle_paire_asymetrique():
    # 3 qubits : seuls les qubits 0 et 2 sont corrélés (copie), le qubit 1 est indépendant.
    probs = np.zeros(8)
    for q1 in (0, 1):
        probs[0b000 | (q1 << 1)] = 0.25
        probs[0b101 | (q1 << 1)] = 0.25
    f = problem_features(probs)
    assert f["mean_mutual_information"] == pytest.approx(1 / 3)  # (1 + 0 + 0) / 3 paires


def test_check_probabilities():
    with pytest.raises(ValueError, match="puissance de 2"):
        check_probabilities([0.5, 0.25, 0.25])
    with pytest.raises(ValueError, match="somme"):
        check_probabilities([0.5, 0.5, 0.5, 0.5])
