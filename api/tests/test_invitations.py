from datetime import timedelta

from conftest import create_project, register
from stochastiq_api.db import utcnow
from stochastiq_api.models import Invitation


def _invite(client, owner, project_id, email="invite@example.test", role="editor"):
    response = client.post(
        f"/projects/{project_id}/invitations", json={"email": email, "role": role}, headers=owner
    )
    assert response.status_code == 201, response.text
    return response.json()


def _token(invitation):
    return invitation["link"].rsplit("/", 1)[1]


def test_creation_et_acceptation(client):
    owner = register(client)
    project_id = create_project(client, owner, "Projet partagé")
    invitation = _invite(client, owner, project_id, "Invite@Example.test")
    assert invitation["link"].startswith("http://front.test/invitations/")
    assert invitation["email"] == "invite@example.test"
    assert invitation["status"] == "pending"
    assert (invitation_expiry := invitation["expires_at"])  # date d'expiration renseignée

    public = client.get(f"/invitations/{_token(invitation)}").json()
    assert public == {
        "project_name": "Projet partagé",
        "email": "invite@example.test",
        "role": "editor",
        "status": "pending",
        "expires_at": invitation_expiry,
    }

    guest = register(client, "invite@example.test")
    accepted = client.post(f"/invitations/{_token(invitation)}/accept", headers=guest)
    assert accepted.status_code == 200
    members = client.get(f"/projects/{project_id}/members", headers=guest).json()
    assert {m["email"]: m["role"] for m in members}["invite@example.test"] == "editor"
    assert client.get(f"/invitations/{_token(invitation)}").json()["status"] == "accepted"
    assert client.post(f"/invitations/{_token(invitation)}/accept", headers=guest).status_code == 409


def test_expiration_sept_jours(client):
    owner = register(client)
    project_id = create_project(client, owner)
    invitation = _invite(client, owner, project_id)
    session = client.app.state.sessionmaker()
    row = session.get(Invitation, invitation["id"])
    assert abs(row.expires_at - (row.created_at + timedelta(days=7))) < timedelta(seconds=5)
    session.close()


def test_mauvais_email(client):
    owner = register(client)
    project_id = create_project(client, owner)
    invitation = _invite(client, owner, project_id, "attendu@example.test")
    other = register(client, "autre@example.test")
    response = client.post(f"/invitations/{_token(invitation)}/accept", headers=other)
    assert response.status_code == 403
    assert client.get(f"/projects/{project_id}", headers=other).status_code == 404


def test_invitation_expiree(client):
    owner = register(client)
    project_id = create_project(client, owner)
    invitation = _invite(client, owner, project_id, "tard@example.test")
    with client.app.state.sessionmaker() as session:
        session.get(Invitation, invitation["id"]).expires_at = utcnow() - timedelta(minutes=1)
        session.commit()
    guest = register(client, "tard@example.test")
    assert client.post(f"/invitations/{_token(invitation)}/accept", headers=guest).status_code == 410
    assert client.get(f"/invitations/{_token(invitation)}").json()["status"] == "expired"
    assert client.get(f"/projects/{project_id}/invitations", headers=owner).json() == []


def test_invitation_revoquee(client):
    owner = register(client)
    project_id = create_project(client, owner)
    invitation = _invite(client, owner, project_id, "revoque@example.test")
    assert client.delete(f"/projects/{project_id}/invitations/{invitation['id']}", headers=owner).status_code == 204
    guest = register(client, "revoque@example.test")
    assert client.post(f"/invitations/{_token(invitation)}/accept", headers=guest).status_code == 409
    assert client.get(f"/projects/{project_id}/invitations", headers=owner).json() == []


def test_doublons_refuses(client):
    owner = register(client, "proprio@example.test")
    project_id = create_project(client, owner)
    _invite(client, owner, project_id, "double@example.test")
    again = client.post(
        f"/projects/{project_id}/invitations", json={"email": "double@example.test", "role": "viewer"}, headers=owner
    )
    assert again.status_code == 409
    member = client.post(
        f"/projects/{project_id}/invitations", json={"email": "proprio@example.test", "role": "viewer"}, headers=owner
    )
    assert member.status_code == 409


def test_jeton_inconnu(client):
    assert client.get("/invitations/inconnu").status_code == 404
    guest = register(client)
    assert client.post("/invitations/inconnu/accept", headers=guest).status_code == 404


def test_acceptation_sans_connexion(client):
    owner = register(client)
    project_id = create_project(client, owner)
    invitation = _invite(client, owner, project_id)
    assert client.post(f"/invitations/{_token(invitation)}/accept").status_code == 401


def test_invitations_isolees_entre_projets(client):
    alice, bob = register(client), register(client)
    alice_project = create_project(client, alice)
    bob_project = create_project(client, bob)
    invitation = _invite(client, alice, alice_project)
    response = client.delete(f"/projects/{bob_project}/invitations/{invitation['id']}", headers=bob)
    assert response.status_code == 404
