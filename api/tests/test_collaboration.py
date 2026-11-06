import pytest

from conftest import add_member, create_project, register
from stochastiq import list_ansatz
from stochastiq_api.models import Run
from stochastiq_api.roles import MIN_ROLE, ROLES, has_role

RUN = {
    "kind": "hardware",
    "params": {"ansatz": "rotation_only", "n_qubits": 2, "layers": 1, "topology": "line", "seed": 0},
}


def _run_id(client, team):
    with client.app.state.sessionmaker() as db:
        run = Run(project_id=team["project_id"], kind="diagnostic", params={}, status="done")
        db.add(run)
        db.commit()
        return run.id


def _pin(client, headers, project_id, layers=1):
    return client.post(
        f"/projects/{project_id}/pins", json={"ansatz": "brick_wall", "n_qubits": 3, "layers": layers}, headers=headers
    )


def _unpin(client, headers, project_id, team):
    pin_id = _pin(client, team["headers"]["owner"], project_id, layers=7).json()["id"]
    return client.delete(f"/projects/{project_id}/pins/{pin_id}", headers=headers)


def _remove_machine(client, headers, project_id, team):
    machine = client.post(
        f"/projects/{project_id}/machines", json={"provider": "IBM", "label": "A retirer"}, headers=team["headers"]["owner"]
    ).json()
    return client.delete(f"/projects/{project_id}/machines/{machine['id']}", headers=headers)


ACTIONS = {
    "run": ("run", lambda c, h, p, t: c.post(f"/projects/{p}/runs", json=RUN, headers=h)),
    "read_runs": ("read", lambda c, h, p, t: c.get(f"/projects/{p}/runs", headers=h)),
    "read_activity": ("read", lambda c, h, p, t: c.get(f"/projects/{p}/activity", headers=h)),
    "comment": (
        "comment",
        lambda c, h, p, t: c.post(f"/projects/{p}/runs/{_run_id(c, t)}/comments", json={"text": "Vu"}, headers=h),
    ),
    "read_pins": ("read", lambda c, h, p, t: c.get(f"/projects/{p}/pins", headers=h)),
    "pin": ("pin", lambda c, h, p, t: _pin(c, h, p)),
    "unpin": ("pin", _unpin),
    "list_machines": ("machines", lambda c, h, p, t: c.get(f"/projects/{p}/machines", headers=h)),
    "add_machine": (
        "machines",
        lambda c, h, p, t: c.post(f"/projects/{p}/machines", json={"provider": "Origin", "label": "Wukong"}, headers=h),
    ),
    "remove_machine": ("machines", _remove_machine),
}


@pytest.mark.parametrize("role", [*ROLES, "outsider"])
@pytest.mark.parametrize("action", list(ACTIONS))
def test_matrice_de_droits_m2(client, team, action, role):
    matrix_action, call = ACTIONS[action]
    response = call(client, team["headers"][role], team["project_id"], team)
    if role == "outsider":
        assert response.status_code == 404, response.text
    elif has_role(role, MIN_ROLE[matrix_action]):
        assert response.status_code < 300, response.text
    else:
        assert response.status_code == 403, response.text


@pytest.mark.parametrize("field", ["secret", "api_key", "token"])
def test_machine_sans_secret(client, team, field):
    owner, project_id = team["headers"]["owner"], team["project_id"]
    response = client.post(
        f"/projects/{project_id}/machines",
        json={"provider": "IBM", "label": "Brisbane", field: "sk-123"},
        headers=owner,
    )
    assert response.status_code == 422
    assert "ne stocke aucune clé" in response.text
    assert "sk-123" not in client.get(f"/projects/{project_id}/machines", headers=owner).text


def test_epingle_en_double(client, team):
    owner, project_id = team["headers"]["owner"], team["project_id"]
    assert _pin(client, owner, project_id).status_code == 201
    assert _pin(client, owner, project_id).status_code == 409


def test_commentaires(client, team):
    viewer, project_id = team["headers"]["viewer"], team["project_id"]
    run_id = _run_id(client, team)
    client.post(f"/projects/{project_id}/runs/{run_id}/comments", json={"text": "  Premier  "}, headers=viewer)
    client.post(f"/projects/{project_id}/runs/{run_id}/comments", json={"text": "Second"}, headers=viewer)
    comments = client.get(f"/projects/{project_id}/runs/{run_id}/comments", headers=viewer).json()
    assert [c["text"] for c in comments] == ["Premier", "Second"]
    assert comments[0]["user"]["name"] == "Utilisateur"
    empty = client.post(f"/projects/{project_id}/runs/{run_id}/comments", json={"text": "   "}, headers=viewer)
    assert empty.status_code == 422


def test_fil_d_activite_ordre_et_contenu(client):
    owner = register(client, name="Ada")
    project_id = create_project(client, owner)
    _, member_id = add_member(client, owner, project_id, "viewer")
    client.patch(f"/projects/{project_id}/members/{member_id}", json={"role": "editor"}, headers=owner)
    _pin(client, owner, project_id)
    client.post(f"/projects/{project_id}/machines", json={"provider": "IBM", "label": "Test"}, headers=owner)
    with client.app.state.sessionmaker() as db:
        run = Run(project_id=project_id, kind="diagnostic", params={}, status="done")
        db.add(run)
        db.commit()
        run_id = run.id
    client.post(f"/projects/{project_id}/runs/{run_id}/comments", json={"text": "Intéressant"}, headers=owner)

    page = client.get(f"/projects/{project_id}/activity", headers=owner).json()
    assert [e["type"] for e in page["items"]] == [
        "comment_added",
        "machine_added",
        "circuit_pinned",
        "role_changed",
        "member_joined",
        "member_invited",
    ]
    assert page["total"] == 6
    by_type = {e["type"]: e for e in page["items"]}
    assert by_type["role_changed"]["payload"] == {
        "user_id": member_id,
        "name": "Utilisateur",
        "old_role": "viewer",
        "new_role": "editor",
    }
    assert by_type["member_invited"]["user"]["name"] == "Ada"
    assert by_type["member_invited"]["payload"]["role"] == "viewer"
    assert by_type["comment_added"]["payload"]["excerpt"] == "Intéressant"
    assert by_type["circuit_pinned"]["payload"] == {"ansatz": "brick_wall", "n_qubits": 3, "layers": 1}
    second = client.get(f"/projects/{project_id}/activity?limit=2&offset=2", headers=owner).json()
    assert [e["type"] for e in second["items"]] == ["circuit_pinned", "role_changed"]


def test_activite_isolee_entre_projets(client):
    alice, bob = register(client), register(client)
    alice_project = create_project(client, alice)
    create_project(client, bob)
    client.post(f"/projects/{alice_project}/invitations", json={"email": "x@example.test", "role": "viewer"}, headers=alice)
    assert client.get(f"/projects/{alice_project}/activity", headers=bob).status_code == 404


def test_catalogue_des_ansatz(client):
    catalog = client.get("/ansatz").json()
    assert [a["name"] for a in catalog] == list_ansatz()
    assert {a["name"]: a["label"] for a in catalog}["data_reuploading"] == "DataReuploading"
    assert {a["name"]: a["parameters"] for a in catalog}["strongly_entangling"] == "3·L·n"
    structure = client.get("/ansatz/hardware_efficient/structure?n_qubits=3&layers=1").json()
    assert structure["n_qubits"] == 3
    assert len(structure["columns"]) == 4
    assert client.get("/ansatz/inconnu/structure?n_qubits=3&layers=1").status_code == 404
    assert client.get("/ansatz/hardware_efficient/structure?n_qubits=9&layers=1").status_code == 422
    assert [t["name"] for t in client.get("/topologies").json()] == ["line", "ring", "full", "heavy_hex"]
