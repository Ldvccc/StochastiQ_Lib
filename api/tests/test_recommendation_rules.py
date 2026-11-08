import pytest

from stochastiq_api.ml.recommendation import decide, overlaps


def c(key, value, low, high, measured=False):
    return {"key": key, "value": value, "low": low, "high": high, "measured": measured}


def test_recouvrement():
    assert overlaps({"low": 0.1, "high": 0.3}, {"low": 0.3, "high": 0.5})
    assert not overlaps({"low": 0.1, "high": 0.2}, {"low": 0.25, "high": 0.5})


def test_quantique_justifie_et_classement():
    result = decide([c("B", 0.20, 0.15, 0.25), c("A", 0.05, 0.02, 0.08)], classical_tvd=0.10, budget=400)
    assert result["ranking"] == ["A", "B"]
    assert result["best"] == "A"
    assert result["verdict"] == "justified"
    assert result["indistinguishable"] == []
    assert result["to_train"] == []


def test_quantique_non_justifie():
    result = decide([c("A", 0.30, 0.25, 0.35), c("B", 0.40, 0.30, 0.50)], classical_tvd=0.10, budget=400)
    assert result["verdict"] == "not_justified"
    assert result["indistinguishable"] == ["B"]


def test_indetermine_et_ansatz_a_entrainer():
    candidates = [c("A", 0.10, 0.05, 0.20), c("B", 0.12, 0.06, 0.25), c("C", 0.13, 0.11, 0.30), c("D", 0.40, 0.35, 0.45)]
    result = decide(candidates, classical_tvd=0.15, budget=400)
    assert result["verdict"] == "undetermined"
    assert result["n_trainings"] == 2
    assert result["to_train"] == ["A", "B"]
    assert result["indistinguishable"] == ["B", "C"]
    assert decide(candidates, classical_tvd=0.15, budget=100)["to_train"] == ["A"]  # au moins un entraînement


def test_entrainement_mesure_prime_et_n_est_pas_a_refaire():
    # A mesuré (intervalle réduit à sa valeur) ; B prédit, mieux placé mais incertain.
    candidates = [c("A", 0.14, 0.14, 0.14, measured=True), c("B", 0.12, 0.08, 0.20)]
    result = decide(candidates, classical_tvd=0.13, budget=400)
    assert result["best"] == "B" and result["verdict"] == "undetermined"
    assert result["to_train"] == ["B"]  # A est déjà entraîné, et 0,13 n'est pas dans [0,14 ; 0,14]
    assert decide([c("A", 0.12, 0.12, 0.12, measured=True), c("B", 0.30, 0.25, 0.35)], 0.13, 400)["verdict"] == "justified"


def test_intervalle_non_fiable_ne_tranche_rien():
    result = decide([c("A", 0.02, None, None), c("B", 0.30, 0.25, 0.35)], classical_tvd=0.10, budget=400)
    assert result["best"] == "A"
    assert result["indistinguishable"] == ["B"]
    assert result["verdict"] == "undetermined"
    assert result["to_train"] == ["A"]


def test_au_moins_deux_ansatz():
    with pytest.raises(ValueError, match="deux ansatz"):
        decide([c("A", 0.1, 0.0, 0.2)], 0.1, 400)
