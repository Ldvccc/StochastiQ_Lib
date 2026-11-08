import pytest

from conftest import create_project, register
from stochastiq_api.ml.service import NO_MODEL
from test_runs import launch, wait_run

GAUSS = {"name": "Gauss 3", "reference": {"distribution": "gaussian", "n_qubits": 3}}


def setup_project(client):
    owner = register(client)
    project_id = create_project(client, owner)
    problem = client.post(f"/projects/{project_id}/problems", json=GAUSS, headers=owner).json()
    return owner, project_id, problem["id"]


def params(problem_id, **change):
    return {
        "problem_id": problem_id,
        "ansatz": ["hardware_efficient", "rotation_only"],
        "layers": 1,
        "n_samples": 50,
        **change,
    }


def run(client, owner, project_id, body):
    created = launch(client, owner, project_id, "recommendation", body)
    assert created.status_code == 202, created.text
    finished = wait_run(client, owner, project_id, created.json()["id"])
    assert finished["status"] == "done", finished["error"]
    return finished


def test_refus_sans_modele(client):
    owner, project_id, problem_id = setup_project(client)
    response = launch(client, owner, project_id, "recommendation", params(problem_id))
    assert response.status_code == 409
    assert response.json()["detail"] == NO_MODEL


def test_recommandation_predite(model_client):
    owner, project_id, problem_id = setup_project(model_client)
    finished = run(model_client, owner, project_id, params(problem_id))
    assert finished["params"]["existing"] == [None, None]
    assert finished["params"]["problem_family"] == "gaussian"
    assert len(finished["params"]["target"]) == 8
    result = finished["result"]
    assert [item["key"] for item in result["items"]] == ["hardware_efficient", "rotation_only"]
    for item in result["items"]:
        assert item["source"] in ("model", "reference")
        assert item["measured"] is None
        assert item["value"] == pytest.approx(item["prediction"]["final_tvd"]["value"])
        assert set(item["diagnostic"]) >= {"expressibility", "entangling_capability", "gradient_mean_variance"}
    classical = result["classical"]
    assert classical["best_tvd"] == min(b["tvd"] for b in classical["baselines"].values())
    decision = result["decision"]
    assert sorted(decision["ranking"]) == ["hardware_efficient", "rotation_only"]
    assert decision["verdict"] in ("justified", "not_justified", "probably_justified", "probably_not_justified", "undetermined")
    for item in result["items"]:
        assert item["evidence"] in ("interval", "margin")
        if item["evidence"] == "margin":
            # Marge : 2 × l'erreur absolue moyenne de validation du cas comparable.
            assert item["margin"] == pytest.approx(2 * item["prediction"]["final_tvd"]["mae"])
    assert decision["n_trainings"] == 2
    assert result["noise_profile"] is None


def test_entrainement_existant_prime(model_client):
    owner, project_id, problem_id = setup_project(model_client)
    training = {"problem_id": problem_id, "ansatz": "hardware_efficient", "layers": 1, "max_iter": 20, "seed": 0}
    trained = wait_run(model_client, owner, project_id, launch(model_client, owner, project_id, "training", training).json()["id"])
    assert trained["status"] == "done", trained["error"]
    finished = run(model_client, owner, project_id, params(problem_id))
    existing = finished["params"]["existing"]
    assert existing[0] == {"run_id": trained["id"], "tvd": trained["result"]["metrics"]["tvd"], "noisy_tvd": None}
    assert existing[1] is None
    item = finished["result"]["items"][0]
    assert item["source"] == "measured"
    assert item["evidence"] == "measured"
    assert item["value"] == pytest.approx(trained["result"]["metrics"]["tvd"])
    assert item["low"] is None and item["high"] is None  # une mesure n'a pas de « borne »
    assert "hardware_efficient" not in finished["result"]["decision"]["to_train"]
    # Autre nombre de couches : l'entraînement ne compte pas.
    other = run(model_client, owner, project_id, params(problem_id, layers=2))
    assert other["params"]["existing"] == [None, None]


def test_sous_bruit(model_client):
    owner, project_id, problem_id = setup_project(model_client)
    training = {
        "problem_id": problem_id, "ansatz": "hardware_efficient", "layers": 1, "max_iter": 20, "seed": 0,
        "evaluate_noise": {"profile": "fort", "topology": "line"},
    }
    trained = wait_run(model_client, owner, project_id, launch(model_client, owner, project_id, "training", training).json()["id"])
    noisy_tvd = trained["result"]["noise"]["metrics"]["tvd"]
    same = run(model_client, owner, project_id, params(problem_id, noise_profile="fort"))
    first = same["result"]["items"][0]
    assert first["source"] == "measured" and first["value"] == pytest.approx(noisy_tvd)
    assert same["result"]["noise_profile"] == {"p1": 1e-2, "p2": 2e-2, "readout": 5e-2}
    assert same["result"]["items"][1]["prediction"]["degradation"] is not None
    other = run(model_client, owner, project_id, params(problem_id, noise_profile="moyen"))
    first = other["result"]["items"][0]
    assert first["source"] == "measured_degradation_predicted"
    expected = trained["result"]["metrics"]["tvd"] + first["prediction"]["degradation"]["value"]
    assert first["value"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"ansatz": ["hardware_efficient"]}, "at least 2"),
        ({"ansatz": ["hardware_efficient"] * 2}, "qu'une fois"),
        ({"budget": 100}, "greater than or equal to 200"),
        ({"budget": 7001}, "less than or equal to 7000"),
        ({"topology": "heavy_hex"}, "'line', 'ring' or 'full'"),
    ],
)
def test_parametres_refuses(model_client, change, message):
    owner, project_id, problem_id = setup_project(model_client)
    response = launch(model_client, owner, project_id, "recommendation", params(problem_id, **change))
    assert response.status_code == 422
    assert message in response.text
