from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import create_project, register
from stochastiq_api.config import Settings
from stochastiq_api.main import create_app
from stochastiq_api.ml.predictor import (
    conformal_margin,
    load_bundle,
    matching_validation,
    predict,
    report_of,
    save_bundle,
    target_rows,
    train_predictor,
)
from stochastiq_api.ml.service import NO_MODEL, feature_row

from conftest import GRID


def test_marge_conforme():
    scores = np.arange(1, 10, dtype=float)  # n = 9, rang ⌈10 × 0,8⌉ = 8
    assert conformal_margin(scores) == 8
    assert conformal_margin(np.array([0.5, 1.0])) == np.inf  # rang 3 > n
    assert conformal_margin(np.array([])) == np.inf


def test_lignes_par_cible():
    frame = pd.read_csv(GRID)
    assert len(target_rows(frame, "final_tvd")) == 756
    assert len(target_rows(frame, "degradation")) == 2268


def test_rapport_de_validation(bundle):
    report = report_of(bundle)
    for target in ("final_tvd", "degradation"):
        validations = report["targets"][target]["validations"]
        assert set(validations) == {"ansatz_laisse_de_cote", "famille_laissee_de_cote", "qubits_2_5_vers_6", "aleatoire"}
        for v in validations.values():
            assert 0 <= v["coverage_raw"] <= 1 and 0 <= v["coverage"] <= 1
            assert v["point_model"] == (v["gain"] >= 0.2)
            assert v["interval_reliable"] == (0.7 <= v["coverage"] <= 0.9)
            assert v["width"] >= v["width_raw"]  # la marge CQR n'est jamais négative ici
        assert validations["ansatz_laisse_de_cote"]["n_folds"] == 7
    assert "models" not in report["targets"]["final_tvd"]


def test_validation_du_cas(bundle):
    spec = bundle["targets"]["final_tvd"]
    known = {"ansatz_fingerprint": "cat:hardware_efficient", "problem_family": "gaussian", "n_qubits": 4}
    assert matching_validation(spec, known) == ("aleatoire", [])
    assert matching_validation(spec, {**known, "ansatz_fingerprint": "custom:0123"})[0] == "ansatz_laisse_de_cote"
    assert matching_validation(spec, {**known, "problem_family": "csv"})[0] == "famille_laissee_de_cote"
    assert matching_validation(spec, {**known, "n_qubits": 8})[0] == "qubits_2_5_vers_6"
    worst, situations = matching_validation(spec, {**known, "problem_family": "csv", "n_qubits": 8})
    assert situations == ["famille_laissee_de_cote", "qubits_2_5_vers_6"] and worst in situations


def test_prediction_et_intervalle(bundle):
    features = {"entropy": 0.6, "support_fraction": 1.0, "max_probability": 0.2, "mean_mutual_information": 0.05}
    row = feature_row("hardware_efficient", 4, 1, features, "gaussian", "moyen", "line")
    for target in ("final_tvd", "degradation"):
        result = predict(bundle, target, row)
        validation = bundle["targets"][target]["validations"][result["validation"]]
        assert result["validation"] == "aleatoire"
        assert result["source"] == ("model" if validation["point_model"] else "reference")
        if result["interval_reliable"]:
            assert result["low"] <= result["high"] and result["interval_message"] is None
        else:
            assert result["low"] is None
            assert result["interval_message"].startswith("Intervalle non")
    custom = predict(bundle, "final_tvd", {**row, "problem_family": "csv"})
    assert custom["validation"] == "famille_laissee_de_cote"


def test_message_d_intervalle_non_fiable(bundle):
    spec = bundle["targets"]["final_tvd"]
    validation = spec["validations"]["famille_laissee_de_cote"]
    original = dict(validation)
    validation.update(interval_reliable=False, coverage=0.524, point_model=True)
    try:
        features = {"entropy": 0.6, "support_fraction": 1.0, "max_probability": 0.2, "mean_mutual_information": 0.05}
        row = feature_row("hardware_efficient", 4, 1, features, "csv")
        result = predict(bundle, "final_tvd", row)
        assert result["interval_message"] == "Intervalle non fiable pour ce cas : couverture mesurée 52,4 %."
    finally:
        validation.clear()
        validation.update(original)


def test_route_sans_modele(client):
    owner = register(client)
    project_id = create_project(client, owner)
    body = {"name": "G", "reference": {"distribution": "gaussian", "n_qubits": 3}}
    problem = client.post(f"/projects/{project_id}/problems", json=body, headers=owner).json()
    response = client.post(f"/projects/{project_id}/predict", json={"problem_id": problem["id"], "ansatz": "rotation_only", "layers": 1}, headers=owner)
    assert response.status_code == 409
    assert response.json()["detail"] == NO_MODEL


def test_route_avec_modele(settings, bundle, tmp_path):
    save_bundle(bundle, tmp_path / "models")
    assert load_bundle(tmp_path / "models") is not None
    settings = Settings(**{**settings.model_dump(), "models_dir": str(tmp_path / "models")})
    from fastapi.testclient import TestClient

    with TestClient(create_app(settings)) as client:
        owner = register(client)
        project_id = create_project(client, owner)
        body = {"name": "G", "reference": {"distribution": "gaussian", "n_qubits": 3}}
        problem = client.post(f"/projects/{project_id}/problems", json=body, headers=owner).json()
        request = {"problem_id": problem["id"], "ansatz": "hardware_efficient", "layers": 2, "noise_profile": "fort"}
        response = client.post(f"/projects/{project_id}/predict", json=request, headers=owner)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["n_qubits"] == 3
        assert result["final_tvd"]["validation"] == "aleatoire"
        assert result["degradation"]["references"]["gate_fidelity"] > 0
        assert result["noisy_tvd"]["value"] == pytest.approx(result["final_tvd"]["value"] + result["degradation"]["value"])
        assert set(result["model"]["targets"]) == {"final_tvd", "degradation"}
        # Lecteur : pas le droit de lancer, donc pas de prédiction.
        viewer_problem = {"problem_id": problem["id"], "ansatz": "hardware_efficient", "layers": 2}
        assert client.post(f"/projects/{project_id}/predict", json=viewer_problem, headers=register(client)).status_code in (403, 404)
        foreign = client.post(f"/projects/{project_id}/predict", json={**viewer_problem, "problem_id": 999}, headers=owner)
        assert foreign.status_code == 422
