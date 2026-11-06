"""Matrice de droits : pour chaque action et chaque rôle, autorisé ou refusé."""

import pytest

from conftest import add_member, create_project, register
from stochastiq_api.roles import MIN_ROLE, ROLES, has_role

ROLE_CASES = [*ROLES, "outsider"]


def _invite(client, headers, project_id):
    return client.post(
        f"/projects/{project_id}/invitations",
        json={"email": "nouvelle@example.test", "role": "viewer"},
        headers=headers,
    )


def _revoke(client, headers, project_id, team):
    owner = team["headers"]["owner"]
    invitation = client.post(
        f"/projects/{project_id}/invitations",
        json={"email": "a-revoquer@example.test", "role": "viewer"},
        headers=owner,
    ).json()
    return client.delete(f"/projects/{project_id}/invitations/{invitation['id']}", headers=headers)


def _remove(client, headers, project_id, team):
    _, user_id = add_member(client, team["headers"]["owner"], project_id, "viewer")
    return client.delete(f"/projects/{project_id}/members/{user_id}", headers=headers)


ACTIONS = {
    "read": lambda c, h, p, t: c.get(f"/projects/{p}", headers=h),
    "read_members": lambda c, h, p, t: c.get(f"/projects/{p}/members", headers=h),
    "edit_project": lambda c, h, p, t: c.patch(f"/projects/{p}", json={"name": "Renommé"}, headers=h),
    "invite": lambda c, h, p, t: _invite(c, h, p),
    "list_invitations": lambda c, h, p, t: c.get(f"/projects/{p}/invitations", headers=h),
    "revoke_invitation": _revoke,
    "manage_members": lambda c, h, p, t: c.patch(
        f"/projects/{p}/members/{t['ids']['viewer']}", json={"title": "CTO"}, headers=h
    ),
    "remove_member": _remove,
    "delete_project": lambda c, h, p, t: c.delete(f"/projects/{p}", headers=h),
}

# Action testée -> action de la matrice de droits.
MATRIX_ACTION = {
    "read": "read",
    "read_members": "read",
    "edit_project": "edit_project",
    "invite": "invite",
    "list_invitations": "invite",
    "revoke_invitation": "invite",
    "manage_members": "manage_members",
    "remove_member": "manage_members",
    "delete_project": "delete_project",
}


@pytest.mark.parametrize("role", ROLE_CASES)
@pytest.mark.parametrize("action", list(ACTIONS))
def test_matrice_de_droits(client, team, action, role):
    response = ACTIONS[action](client, team["headers"][role], team["project_id"], team)
    if role == "outsider":
        assert response.status_code == 404, response.text
    elif has_role(role, MIN_ROLE[MATRIX_ACTION[action]]):
        assert response.status_code < 300, response.text
    else:
        assert response.status_code == 403, response.text
        assert "Droit insuffisant" in response.json()["detail"]


def test_chaque_role_a_au_moins_un_refus_et_une_autorisation():
    # Garantit que la matrice testée couvre bien les deux cas pour chaque rôle.
    for role in ROLES:
        allowed = [a for a in ACTIONS if has_role(role, MIN_ROLE[MATRIX_ACTION[a]])]
        assert allowed
        if role != "owner":
            assert len(allowed) < len(ACTIONS)


def test_titre_sans_effet_sur_les_droits(client, team):
    owner, project_id = team["headers"]["owner"], team["project_id"]
    viewer_id = team["ids"]["viewer"]
    response = client.patch(
        f"/projects/{project_id}/members/{viewer_id}", json={"title": "CEO"}, headers=owner
    )
    assert response.json()["title"] == "CEO"
    assert response.json()["role"] == "viewer"
    viewer = team["headers"]["viewer"]
    assert client.patch(f"/projects/{project_id}", json={"name": "X"}, headers=viewer).status_code == 403


def test_changement_de_role(client, team):
    owner, project_id = team["headers"]["owner"], team["project_id"]
    viewer_id = team["ids"]["viewer"]
    response = client.patch(
        f"/projects/{project_id}/members/{viewer_id}", json={"role": "editor"}, headers=owner
    )
    assert response.json()["role"] == "editor"


def test_role_inconnu_refuse(client, team):
    owner, project_id = team["headers"]["owner"], team["project_id"]
    response = client.patch(
        f"/projects/{project_id}/members/{team['ids']['viewer']}", json={"role": "admin"}, headers=owner
    )
    assert response.status_code == 422


def test_matrice_servie_par_l_api(client):
    body = client.get("/roles").json()
    assert [r["name"] for r in body["roles"]] == list(ROLES)
    assert {p["action"]: p["min_role"] for p in body["permissions"]} == MIN_ROLE


def test_dernier_proprietaire_protege(client):
    owner = register(client)
    project_id = create_project(client, owner)
    owner_id = client.get("/me", headers=owner).json()["id"]
    demote = client.patch(f"/projects/{project_id}/members/{owner_id}", json={"role": "editor"}, headers=owner)
    assert demote.status_code == 409
    assert client.delete(f"/projects/{project_id}/members/{owner_id}", headers=owner).status_code == 409


def test_proprietaire_retrogradable_s_il_en_reste_un(client):
    owner = register(client)
    project_id = create_project(client, owner)
    owner_id = client.get("/me", headers=owner).json()["id"]
    add_member(client, owner, project_id, "owner")
    demote = client.patch(f"/projects/{project_id}/members/{owner_id}", json={"role": "editor"}, headers=owner)
    assert demote.status_code == 200
