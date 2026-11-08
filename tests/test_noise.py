import numpy as np
import pytest

pytest.importorskip("qiskit_aer")

from stochastiq import build_ansatz  # noqa: E402
from stochastiq.gradients import batched_probabilities  # noqa: E402
from stochastiq.noise import PROFILES, noisy_probabilities, noisy_tvd, resolve_profile  # noqa: E402

NO_NOISE = {"p1": 0.0, "p2": 0.0, "readout": 0.0}


@pytest.mark.parametrize("topology", ["line", "ring", "full"])
def test_sans_bruit_identique_a_la_sortie_ideale(topology):
    # Ansatz en anneau : sur une ligne, le routage permute les qubits ; l'ordre logique doit être rétabli.
    qc = build_ansatz("data_reuploading", 4, 2)
    theta = np.random.default_rng(0).uniform(0, 2 * np.pi, qc.num_parameters)
    ideal = batched_probabilities(qc, theta)[0]
    np.testing.assert_allclose(noisy_probabilities(qc, theta, NO_NOISE, topology, seed=0), ideal, atol=1e-9)
    assert noisy_tvd(qc, NO_NOISE, topology, n_samples=3, seed=0)["mean_tvd"] == pytest.approx(0, abs=1e-9)


def test_tvd_croissante_avec_le_taux_d_erreur():
    qc = build_ansatz("hardware_efficient", 3, 2)
    tvds = [noisy_tvd(qc, name, "line", n_samples=5, seed=1)["mean_tvd"] for name in ("faible", "moyen", "fort")]
    assert 0 < tvds[0] < tvds[1] < tvds[2]


def test_reproductible():
    qc = build_ansatz("hardware_efficient", 3, 1)
    a = noisy_tvd(qc, "moyen", "ring", n_samples=4, seed=7)
    b = noisy_tvd(qc, "moyen", "ring", n_samples=4, seed=7)
    assert a["tvds"] == b["tvds"]
    assert a["profile"] == PROFILES["moyen"]


def test_erreur_de_lecture_seule():
    # rotation_only à paramètres nuls : état |000> ; seule l'erreur de lecture agit.
    qc = build_ansatz("rotation_only", 3, 1)
    probs = noisy_probabilities(qc, np.zeros(3), {"p1": 0.0, "p2": 0.0, "readout": 0.1}, "full", seed=0)
    assert probs[0] == pytest.approx(0.9**3)
    assert probs[0b001] == pytest.approx(0.1 * 0.9**2)  # un seul bit lu à tort, ici le qubit 0
    assert probs.sum() == pytest.approx(1)


def test_ordre_logique_des_qubits():
    qc = build_ansatz("rotation_only", 3, 1)
    probs = noisy_probabilities(qc, [np.pi, 0, 0], NO_NOISE, "line", seed=0)  # RY(π) sur le qubit 0
    assert probs.argmax() == 0b001


def test_profils():
    assert resolve_profile("fort") == {"p1": 1e-2, "p2": 2e-2, "readout": 5e-2}
    assert resolve_profile({"p1": 0.001, "p2": 0.01, "readout": 0.02})["p2"] == 0.01
    with pytest.raises(ValueError, match="Profil de bruit inconnu"):
        resolve_profile("extreme")
    with pytest.raises(ValueError, match="entre 0 et 0.5"):
        resolve_profile({"p1": -0.1, "p2": 0.0, "readout": 0.0})
    with pytest.raises(ValueError, match="exactement p1, p2 et readout"):
        resolve_profile({"p1": 0.1})


def test_hexagone_lourd_refuse():
    qc = build_ansatz("hardware_efficient", 3, 1)
    with pytest.raises(ValueError, match="hexagone lourd"):
        noisy_probabilities(qc, np.zeros(qc.num_parameters), "moyen", "heavy_hex")
    with pytest.raises(ValueError, match="Topologie inconnue"):
        noisy_probabilities(qc, np.zeros(qc.num_parameters), "moyen", "etoile")
