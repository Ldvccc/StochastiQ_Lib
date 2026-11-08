import pytest

from conftest import create_project, register
from test_runs import launch, wait_run

PROBLEM = {"name": "Cible 2 qubits", "format": "probabilities", "content": "00,0.4\n01,0.1\n10,0.1\n11,0.4\n"}


@pytest.fixture
def setup(client):
    owner = register(client)
    project_id = create_project(client, owner)
    problem = client.post(f"/projects/{project_id}/problems/csv", json=PROBLEM, headers=owner).json()
    return owner, project_id, problem


def _params(problem_id, **change):
    return {"problem_id": problem_id, "ansatz": "hardware_efficient", "layers": 2, "max_iter": 30, "seed": 0, **change}


def test_cycle_de_vie_d_un_entrainement(client, setup):
    owner, project_id, problem = setup
    created = launch(client, owner, project_id, "training", _params(problem["id"]))
    assert created.status_code == 202, created.text
    params = created.json()["params"]
    assert params["target"] == pytest.approx([0.4, 0.1, 0.1, 0.4])
    assert params["n_qubits"] == 2
    assert params["problem_name"] == "Cible 2 qubits"
    run = wait_run(client, owner, project_id, created.json()["id"])
    assert run["status"] == "done", run["error"]
    result = run["result"]
    assert len(result["history"]) == 30
    assert set(result["metrics"]) == {"kl", "tvd", "hellinger"}
    assert set(result["baselines"]) == {"independent", "chow_liu"}
    assert result["baselines"]["independent"]["metrics"]["tvd"] == pytest.approx(0.3)
    assert result["baselines"]["chow_liu"]["n_parameters"] == 3
    assert result["n_parameters"] == 8
    assert sum(result["probabilities"]) == pytest.approx(1)
    assert set(result["problem_features"]) >= {"entropy", "mean_mutual_information"}


def test_entrainement_avec_tirages_et_spsa(client, setup):
    owner, project_id, problem = setup
    params = _params(problem["id"], loss="tvd", optimizer="spsa", learning_rate=0.5, shots=1000)
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "training", params).json()["id"])
    assert run["status"] == "done", run["error"]
    assert run["result"]["optimizer"] == "spsa"


@pytest.mark.parametrize(
    "change, message",
    [
        ({"loss": "tvd", "optimizer": "adam"}, "SPSA ou COBYLA"),
        ({"max_iter": 9}, "greater than or equal to 10"),
        ({"max_iter": 1001}, "less than or equal to 1000"),
        ({"shots": 50}, "greater than or equal to 100"),
        ({"learning_rate": 0}, "greater than 0"),
        ({"layers": 9}, "less than or equal to 8"),
    ],
)
def test_parametres_refuses(client, setup, change, message):
    owner, project_id, problem = setup
    response = launch(client, owner, project_id, "training", _params(problem["id"], **change))
    assert response.status_code == 422
    assert message in response.text


def test_probleme_d_un_autre_projet(client, setup):
    owner, project_id, _ = setup
    other = register(client)
    other_project = create_project(client, other)
    foreign = client.post(f"/projects/{other_project}/problems/csv", json=PROBLEM, headers=other).json()
    response = launch(client, owner, project_id, "training", _params(foreign["id"]))
    assert response.status_code == 422
    assert "introuvable dans ce projet" in response.text
    assert launch(client, owner, project_id, "training", _params(9999)).status_code == 422


def test_ansatz_personnalise_de_taille_incompatible(client, setup):
    owner, project_id, problem = setup
    spec = {"rotations": ["ry"], "entangler": "custom", "pairs": [[0, 1], [1, 2]]}
    custom = client.post(f"/projects/{project_id}/custom-ansatz", json={"name": "3 qubits", "format": "spec", "spec": spec}, headers=owner).json()
    response = launch(client, owner, project_id, "training", _params(problem["id"], ansatz={"custom_id": custom["id"]}))
    assert response.status_code == 422
    assert "fixe 3 qubits, mais le run en demande 2" in response.text


def test_lecteur_ne_lance_pas_d_entrainement(client, team):
    owner, project_id = team["headers"]["owner"], team["project_id"]
    problem = client.post(f"/projects/{project_id}/problems/csv", json=PROBLEM, headers=owner).json()
    response = launch(client, team["headers"]["viewer"], project_id, "training", _params(problem["id"]))
    assert response.status_code == 403
