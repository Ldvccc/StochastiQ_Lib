import pytest

from conftest import create_project, register
from stochastiq import gaussian, list_distributions
from stochastiq_api.problem_import import MAX_CSV_ROWS
from stochastiq_api.roles import ROLES, has_role

REFERENCE = {"name": "Gaussienne 3 qubits", "reference": {"distribution": "gaussian", "n_qubits": 3}}


def _create(client, headers, project_id, body=REFERENCE):
    return client.post(f"/projects/{project_id}/problems", json=body, headers=headers)


def _csv(client, headers, project_id, **body):
    return client.post(f"/projects/{project_id}/problems/csv", json={"name": "Import", **body}, headers=headers)


@pytest.fixture
def owner_project(client):
    owner = register(client)
    return owner, create_project(client, owner)


def test_creation_depuis_une_reference(client, owner_project):
    owner, project_id = owner_project
    response = _create(client, owner, project_id)
    assert response.status_code == 201, response.text
    problem = response.json()
    assert problem["origin"] == "reference"
    assert problem["n_qubits"] == 3
    assert problem["probabilities"] == pytest.approx(gaussian(3).tolist())
    assert problem["source_params"] == {"distribution": "gaussian", "n_qubits": 3, "seed": None}
    assert set(problem["features"]) == {"n_qubits", "entropy", "support_fraction", "max_probability", "mean_mutual_information"}
    listed = client.get(f"/projects/{project_id}/problems", headers=owner).json()
    assert [p["name"] for p in listed] == ["Gaussienne 3 qubits"]
    assert "probabilities" not in listed[0]
    events = client.get(f"/projects/{project_id}/activity", headers=owner).json()["items"]
    assert events[0]["type"] == "problem_added"
    assert events[0]["payload"] == {"problem_id": problem["id"], "name": "Gaussienne 3 qubits", "n_qubits": 3, "origin": "reference"}


def test_ising_avec_graine_reproductible(client, owner_project):
    owner, project_id = owner_project
    body = {"name": "Ising", "reference": {"distribution": "ising_boltzmann", "n_qubits": 4, "seed": 7}}
    a = _create(client, owner, project_id, body).json()["probabilities"]
    b = _create(client, owner, project_id, body).json()["probabilities"]
    assert a == b


@pytest.mark.parametrize(
    "reference",
    [
        {"distribution": "poisson", "n_qubits": 3},
        {"distribution": "gaussian", "n_qubits": 9},
        {"distribution": "gaussian", "n_qubits": 1},
        {"distribution": "gaussian", "n_qubits": 3, "mu": 2},
    ],
)
def test_reference_invalide(client, owner_project, reference):
    owner, project_id = owner_project
    assert _create(client, owner, project_id, {"name": "x", "reference": reference}).status_code == 422


def test_bars_and_stripes_hors_tailles(client, owner_project):
    owner, project_id = owner_project
    response = _create(client, owner, project_id, {"name": "BAS", "reference": {"distribution": "bars_and_stripes", "n_qubits": 5}})
    assert response.status_code == 422
    assert "Bars-and-Stripes" in response.json()["detail"]


def test_csv_probabilites(client, owner_project):
    owner, project_id = owner_project
    content = "bitstring,probabilite\n00,0.25\n11,0.75\n"
    problem = _csv(client, owner, project_id, format="probabilities", content=content).json()
    assert problem["probabilities"] == pytest.approx([0.25, 0, 0, 0.75])
    assert problem["origin"] == "csv"
    assert problem["source_params"] == {"format": "probabilities", "rows": 2}
    assert "content" not in problem["source_params"]


@pytest.mark.parametrize(
    "content, message",
    [
        ("00,0.5\n11,0.4\n", "somme"),
        ("00,1.2\n11,-0.2\n", "négative"),
        ("00,0.5\n00,0.5\n", "plusieurs fois"),
        ("00,0.5\n2,0.5\n", "Ligne 2 invalide"),
        ("", "String should have at least 1 character"),
        ("bitstring,probabilite\n", "vide"),
    ],
)
def test_csv_probabilites_refuse(client, owner_project, content, message):
    owner, project_id = owner_project
    response = _csv(client, owner, project_id, format="probabilities", content=content)
    assert response.status_code == 422
    assert message in response.text


def test_csv_echantillons(client, owner_project):
    owner, project_id = owner_project
    content = "prix,volume\n0.0,3.0\n0.0,3.0\n9.9,0.0\n"
    problem = _csv(
        client, owner, project_id, format="samples", content=content, n_qubits=4, ranges=[[0, 10], [0, 4]], encoding="gray"
    ).json()
    assert problem["probabilities"][0 | (2 << 2)] == pytest.approx(2 / 3)
    assert problem["source_params"] == {"format": "samples", "rows": 3, "n_qubits": 4, "ranges": [[0, 10], [0, 4]], "encoding": "gray"}


@pytest.mark.parametrize(
    "body, message",
    [
        ({"content": "0.5\n"}, "demande n_qubits"),
        ({"content": "0.5,1\n", "n_qubits": 3, "ranges": [[0, 1], [0, 1]]}, "ne se répartissent pas"),
        ({"content": "1.5\n", "n_qubits": 2, "ranges": [[0, 1]]}, "sortent de l'intervalle"),
        ({"content": "0.5\n0.2,0.3\n", "n_qubits": 2, "ranges": [[0, 1]]}, "Ligne 2 invalide"),
    ],
)
def test_csv_echantillons_refuse(client, owner_project, body, message):
    owner, project_id = owner_project
    response = _csv(client, owner, project_id, format="samples", **body)
    assert response.status_code == 422
    assert message in response.text


def test_csv_tailles_maximales(client, owner_project):
    owner, project_id = owner_project
    too_many = "0.5\n" * (MAX_CSV_ROWS + 1)
    response = _csv(client, owner, project_id, format="samples", content=too_many, n_qubits=2, ranges=[[0, 1]])
    assert response.status_code == 422
    assert "100000 lignes" in response.text
    too_big = "0.123456789\n" * 90_000  # environ 1,08 Mo
    assert _csv(client, owner, project_id, format="samples", content=too_big, n_qubits=2, ranges=[[0, 1]]).status_code == 422


@pytest.mark.parametrize("role", [*ROLES, "outsider"])
def test_droits(client, team, role):
    headers, project_id = team["headers"][role], team["project_id"]
    owner = team["headers"]["owner"]
    existing = _create(client, owner, project_id).json()["id"]
    read = client.get(f"/projects/{project_id}/problems/{existing}", headers=headers)
    create = _create(client, headers, project_id)
    rename = client.patch(f"/projects/{project_id}/problems/{existing}", json={"name": "Renommé"}, headers=headers)
    delete = client.delete(f"/projects/{project_id}/problems/{existing}", headers=headers)
    if role == "outsider":
        assert {read.status_code, create.status_code, rename.status_code, delete.status_code} == {404}
        return
    assert read.status_code == 200
    expected = 201 if has_role(role, "editor") else 403
    assert create.status_code == expected
    assert rename.status_code == (200 if has_role(role, "editor") else 403)
    assert delete.status_code == (204 if has_role(role, "editor") else 403)


def test_isolation(client, owner_project):
    owner, project_id = owner_project
    problem_id = _create(client, owner, project_id).json()["id"]
    other = register(client)
    other_project = create_project(client, other)
    assert client.get(f"/projects/{other_project}/problems/{problem_id}", headers=other).status_code == 404


def test_catalogue_des_distributions(client):
    catalog = client.get("/distributions").json()
    assert [d["name"] for d in catalog] == list_distributions()
    assert {d["name"]: d["qubits"] for d in catalog}["bars_and_stripes"] == [4, 6]
    assert [d["name"] for d in catalog if d["random"]] == ["ising_boltzmann"]
