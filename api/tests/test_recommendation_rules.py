import pytest

from stochastiq_api.ml.recommendation import _compared, decide, overlaps


def measured(key, value):
    return {"key": key, "value": value, "evidence": "measured", "low": None, "high": None, "margin": None}


def interval(key, value, low, high):
    return {"key": key, "value": value, "evidence": "interval", "low": low, "high": high, "margin": None}


def margin(key, value, m):
    return {"key": key, "value": value, "evidence": "margin", "low": None, "high": None, "margin": m}


def test_recouvrement():
    assert overlaps({"low": 0.1, "high": 0.3}, {"low": 0.3, "high": 0.5})
    assert not overlaps({"low": 0.1, "high": 0.2}, {"low": 0.25, "high": 0.5})


# ---- Valeur mesurée : règle des 10 % ----


def test_cas_reel_mesure_equivalent():
    # HardwareEfficient entraîné sur « Gaussienne 4 qubits » : 0,0585 contre 0,0588 (Chow-Liu), soit 0,5 % d'écart.
    result = decide([measured("hardware_efficient", 0.0585), interval("rotation_only", 0.30, 0.25, 0.35)], 0.0588, 400)
    assert result["best"] == "hardware_efficient"
    assert result["evidence"] == "measured"
    assert result["verdict"] == "equivalent"
    assert result["to_train"] == []


def test_mesure_justifie_sous_90_pourcent():
    assert decide([measured("A", 0.052), measured("B", 0.3)], 0.0588, 400)["verdict"] == "justified"  # 0,052 < 0,0529


def test_mesure_non_justifie_au_dessus_de_110_pourcent():
    assert decide([measured("A", 0.066), measured("B", 0.3)], 0.0588, 400)["verdict"] == "not_justified"  # 0,066 > 0,0647


def test_mesure_bornes_des_10_pourcent():
    # 0,9 × 0,5 et 1,1 × 0,5 sont exactement les flottants 0,45 et 0,55 (bornes non strictes : équivalent).
    assert 0.9 * 0.5 == 0.45 and 1.1 * 0.5 == 0.55
    assert decide([measured("A", 0.45), measured("B", 0.9)], 0.5, 400)["verdict"] == "equivalent"
    assert decide([measured("A", 0.55), measured("B", 0.9)], 0.5, 400)["verdict"] == "equivalent"


# ---- Valeur prédite avec intervalle fiable : règle inchangée ----


def test_intervalle_justifie_et_classement():
    result = decide([interval("B", 0.20, 0.15, 0.25), interval("A", 0.05, 0.02, 0.08)], 0.10, 400)
    assert result["ranking"] == ["A", "B"]
    assert result["verdict"] == "justified"
    assert result["indistinguishable"] == []


def test_intervalle_non_justifie():
    result = decide([interval("A", 0.30, 0.25, 0.35), interval("B", 0.40, 0.30, 0.50)], 0.10, 400)
    assert result["verdict"] == "not_justified"
    assert result["indistinguishable"] == ["B"]


def test_intervalle_indetermine_et_ansatz_a_entrainer():
    candidates = [
        interval("A", 0.10, 0.05, 0.20), interval("B", 0.12, 0.06, 0.25),
        interval("C", 0.13, 0.11, 0.30), interval("D", 0.40, 0.35, 0.45),
    ]
    result = decide(candidates, 0.15, 400)
    assert result["verdict"] == "undetermined"
    assert result["n_trainings"] == 2
    assert result["to_train"] == ["A", "B"]
    assert result["indistinguishable"] == ["B", "C"]
    assert decide(candidates, 0.15, 100)["to_train"] == ["A"]  # au moins un entraînement


# ---- Valeur prédite sans intervalle : marge de 2 × l'erreur moyenne ----


def test_marge_probablement_justifie():
    result = decide([margin("A", 0.05, 0.02), interval("B", 0.30, 0.25, 0.35)], 0.10, 400)
    assert result["verdict"] == "probably_justified"  # 0,05 + 0,02 < 0,10


def test_marge_probablement_non_justifie():
    result = decide([margin("A", 0.20, 0.04), margin("B", 0.30, 0.04)], 0.10, 400)
    assert result["verdict"] == "probably_not_justified"  # 0,20 − 0,04 > 0,10


def test_marge_indeterminee():
    result = decide([margin("A", 0.09, 0.04), margin("B", 0.30, 0.04)], 0.10, 400)
    assert result["verdict"] == "undetermined"
    assert result["to_train"] == ["A"]  # [0,05 ; 0,13] contient 0,10 ; B ([0,26 ; 0,34]) non


def test_une_mesure_n_est_pas_a_refaire():
    result = decide([interval("B", 0.12, 0.08, 0.20), measured("A", 0.14)], 0.13, 400)
    assert result["best"] == "B" and result["verdict"] == "undetermined"
    assert result["to_train"] == ["B"]


def test_au_moins_deux_ansatz():
    with pytest.raises(ValueError, match="deux ansatz"):
        decide([measured("A", 0.1)], 0.1, 400)


# ---- Nature de la preuve d'un ansatz (_compared) ----


def prediction(value, reliable, mae, low=None, high=None, message=None):
    return {"value": value, "low": low, "high": high, "interval_reliable": reliable, "mae": mae, "source": "model",
            "interval_message": message}


def test_preuve_selon_le_cas():
    final_ok = prediction(0.10, True, 0.05, 0.05, 0.20)
    final_ko = prediction(0.10, False, 0.07, message="Intervalle non fiable pour ce cas : couverture mesurée 52,4 %.")
    degradation_ko = prediction(0.02, False, 0.02, message="Intervalle non fiable pour ce cas : couverture mesurée 66,8 %.")
    assert _compared({"final_tvd": final_ok, "degradation": None}, None, False, 0.1)["evidence"] == "interval"
    sans_intervalle = _compared({"final_tvd": final_ko, "degradation": None}, None, False, 0.1)
    assert sans_intervalle["evidence"] == "margin" and sans_intervalle["margin"] == pytest.approx(0.14)
    noisy = {"value": 0.12, "low": None, "high": None, "interval_reliable": False}
    combine = _compared({"final_tvd": final_ko, "degradation": degradation_ko, "noisy_tvd": noisy}, None, True, 0.1)
    assert combine["margin"] == pytest.approx(2 * (0.07 + 0.02))
    mesure = {"run_id": 3, "tvd": 0.06, "noisy_tvd": None}
    assert _compared({"final_tvd": final_ko, "degradation": None}, mesure, False, 0.1)["evidence"] == "measured"


def test_mesure_et_degradation_predite_sans_intervalle():
    # Marge = 0,1 × meilleure TVD classique (une seule initialisation) + 2 × MAE de la dégradation.
    final_ko = prediction(0.10, False, 0.07)
    degradation_ko = prediction(0.02, False, 0.02, message="Intervalle non fiable pour ce cas : couverture mesurée 66,8 %.")
    noisy = {"value": 0.12, "low": None, "high": None, "interval_reliable": False}
    mesure = {"run_id": 3, "tvd": 0.06, "noisy_tvd": None}
    partielle = _compared({"final_tvd": final_ko, "degradation": degradation_ko, "noisy_tvd": noisy}, mesure, True, 0.0588)
    assert partielle["evidence"] == "margin"
    assert partielle["source"] == "measured_degradation_predicted"
    assert partielle["value"] == pytest.approx(0.08)  # 0,06 mesuré + 0,02 prédit
    assert partielle["margin"] == pytest.approx(0.1 * 0.0588 + 2 * 0.02)
    # Avec cette marge, 0,08 contre 0,0588 : 0,08 − 0,04588 = 0,034 n'est pas au-dessus de 0,0588, donc indéterminé.
    candidat = {"key": "A", **{k: partielle[k] for k in ("value", "low", "high", "margin", "evidence")}}
    autre = {"key": "B", "value": 0.3, "evidence": "interval", "low": 0.25, "high": 0.35, "margin": None}
    assert decide([candidat, autre], 0.0588, 400)["verdict"] == "undetermined"


def test_mesure_et_degradation_predite_avec_intervalle():
    # TVD mesurée 0,0585, dégradation [0 ; 0,001], classique 0,0597 : l'intervalle est élargi de 0,1 × 0,0597 de chaque côté.
    degradation_ok = prediction(0.0005, True, 0.01, low=0.0, high=0.001)
    final = prediction(0.06, True, 0.05, 0.03, 0.09)
    noisy = {"value": 0.0605, "low": 0.03, "high": 0.091, "interval_reliable": True}
    mesure = {"run_id": 4, "tvd": 0.0585, "noisy_tvd": None}
    item = _compared({"final_tvd": final, "degradation": degradation_ok, "noisy_tvd": noisy}, mesure, True, 0.0597)
    assert item["evidence"] == "interval"
    assert item["source"] == "measured_degradation_predicted"
    assert item["low"] == pytest.approx(0.0585 + 0.0 - 0.00597)
    assert item["high"] == pytest.approx(0.0585 + 0.001 + 0.00597)
    candidat = {"key": "hardware_efficient", **{k: item[k] for k in ("value", "low", "high", "margin", "evidence")}}
    autre = {"key": "rotation_only", "value": 0.3, "evidence": "interval", "low": 0.25, "high": 0.35, "margin": None}
    verdict = decide([candidat, autre], 0.0597, 400)["verdict"]
    assert verdict in ("equivalent", "undetermined")
    assert verdict != "justified"  # sans l'élargissement, la borne haute 0,0595 < 0,0597 aurait donné « se justifie »
