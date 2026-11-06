from conftest import create_project, register


def test_creation_et_liste(client):
    alice = register(client)
    response = client.post("/projects", json={"name": "Étude QCBM", "description": "Test"}, headers=alice)
    assert response.status_code == 201
    project = response.json()
    assert project["slug"] == "etude-qcbm"
    assert project["role"] == "owner"
    assert [p["id"] for p in client.get("/projects", headers=alice).json()] == [project["id"]]


def test_slug_unique(client):
    alice = register(client)
    create_project(client, alice, "Démo")
    second = client.post("/projects", json={"name": "Démo"}, headers=alice).json()
    assert second["slug"] == "demo-2"


def test_isolation_entre_projets(client):
    alice, bob = register(client), register(client)
    alice_project = create_project(client, alice, "Projet d'Alice")
    create_project(client, bob, "Projet de Bob")
    assert [p["name"] for p in client.get("/projects", headers=bob).json()] == ["Projet de Bob"]
    for method, path in [
        ("get", f"/projects/{alice_project}"),
        ("get", f"/projects/{alice_project}/members"),
        ("patch", f"/projects/{alice_project}"),
        ("delete", f"/projects/{alice_project}"),
    ]:
        kwargs = {"json": {"name": "x"}} if method == "patch" else {}
        assert getattr(client, method)(path, headers=bob, **kwargs).status_code == 404


def test_projet_inexistant(client):
    alice = register(client)
    assert client.get("/projects/999", headers=alice).status_code == 404


def test_suppression_en_cascade(client):
    alice = register(client)
    project_id = create_project(client, alice)
    client.post(
        f"/projects/{project_id}/invitations", json={"email": "x@example.test", "role": "viewer"}, headers=alice
    )
    assert client.delete(f"/projects/{project_id}", headers=alice).status_code == 204
    assert client.get("/projects", headers=alice).json() == []
    assert client.get(f"/projects/{project_id}", headers=alice).status_code == 404


def test_validation_des_entrees(client):
    alice = register(client)
    assert client.post("/projects", json={"name": ""}, headers=alice).status_code == 422
    assert client.post("/projects", json={"name": "x" * 101}, headers=alice).status_code == 422
    assert client.post("/projects", json={"name": "ok", "slug": "force"}, headers=alice).status_code == 422
