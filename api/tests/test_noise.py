import pytest

from conftest import create_project, register
from test_runs import launch, wait_run
from test_training import PROBLEM

NO_NOISE = {"p1": 0.0, "p2": 0.0, "readout": 0.0}


@pytest.fixture
def owner_project(client):
    owner = register(client)
    return owner, create_project(client, owner)


def _params(**change):
    return {"ansatz": "hardware_efficient", "n_qubits": 3, "layers": 2, "profile": "moyen", "n_samples": 4, "seed": 0, **change}


def test_run_bruit(client, owner_project):
    owner, project_id = owner_project
    created = launch(client, owner, project_id, "noise", _params())
    assert created.status_code == 202, created.text
    run = wait_run(client, owner, project_id, created.json()["id"])
    assert run["status"] == "done", run["error"]
    result = run["result"]
    assert len(result["tvds"]) == 4
    assert 0 < result["mean_tvd"] < 1
    assert result["profile"] == {"p1": 1e-3, "p2": 5e-3, "readout": 1e-2}
    assert result["topology"] == "line"


def test_run_bruit_profil_personnalise_nul(client, owner_project):
    owner, project_id = owner_project
    created = launch(client, owner, project_id, "noise", _params(profile=NO_NOISE, topology="ring"))
    run = wait_run(client, owner, project_id, created.json()["id"])
    assert run["status"] == "done", run["error"]
    assert run["result"]["mean_tvd"] == pytest.approx(0, abs=1e-9)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"topology": "heavy_hex"}, "'line', 'ring' or 'full'"),
        ({"profile": "extreme"}, "faible"),
        ({"profile": {"p1": 0.6, "p2": 0.0, "readout": 0.0}}, "less than or equal to 0.5"),
        ({"profile": {"p1": 0.1}}, "Field required"),
        ({"n_samples": 201}, "less than or equal to 200"),
    ],
)
def test_parametres_refuses(client, owner_project, change, message):
    owner, project_id = owner_project
    response = launch(client, owner, project_id, "noise", _params(**change))
    assert response.status_code == 422
    assert message in response.text


def test_diagnostic_avec_degradation_sous_bruit(client, owner_project):
    owner, project_id = owner_project
    params = {"ansatz": "hardware_efficient", "n_qubits": 2, "layers": 1, "n_samples": 50, "noise_profile": "fort"}
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "diagnostic", params).json()["id"])
    assert run["status"] == "done", run["error"]
    assert len(run["result"]["noise"]["tvds"]) == 20
    assert run["result"]["noise"]["mean_tvd"] > 0
    params.pop("noise_profile")
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "diagnostic", params).json()["id"])
    assert run["result"]["noise"] is None


def test_entrainement_evalue_sous_bruit(client, owner_project):
    owner, project_id = owner_project
    problem = client.post(f"/projects/{project_id}/problems/csv", json=PROBLEM, headers=owner).json()
    base = {"problem_id": problem["id"], "ansatz": "hardware_efficient", "layers": 2, "max_iter": 30, "seed": 0}
    exact = wait_run(client, owner, project_id, launch(client, owner, project_id, "training", base).json()["id"])
    assert exact["result"]["noise"] is None
    params = {**base, "evaluate_noise": {"profile": "fort", "topology": "line"}}
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "training", params).json()["id"])
    assert run["status"] == "done", run["error"]
    noise = run["result"]["noise"]
    assert noise["profile"] == "fort"
    assert sum(noise["probabilities"]) == pytest.approx(1)
    # Mêmes paramètres appris (même graine) : seule l'évaluation finale change.
    assert run["result"]["params"] == exact["result"]["params"]
    assert noise["metrics"]["tvd"] != pytest.approx(run["result"]["metrics"]["tvd"])
