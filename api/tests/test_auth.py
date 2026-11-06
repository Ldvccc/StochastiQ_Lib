import logging

import pytest

from conftest import PASSWORD, register
from stochastiq_api.config import DEFAULT_SECRET_KEY, Settings
from stochastiq_api.main import create_app
from stochastiq_api.security import MaskInvitationTokens


def test_inscription_et_connexion(client):
    response = client.post(
        "/auth/register",
        json={"email": "Alice@Example.TEST", "name": "Alice", "password": PASSWORD},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.test"
    assert "password" not in body and "password_hash" not in body

    login = client.post("/auth/login", json={"email": "alice@example.test", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["expires_in"] == 12 * 3600
    me = client.get("/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["name"] == "Alice"


def test_mot_de_passe_trop_court_refuse(client):
    response = client.post(
        "/auth/register", json={"email": "b@example.test", "name": "B", "password": "9-signes!"}
    )
    assert response.status_code == 422


def test_email_deja_utilise(client):
    register(client, "c@example.test")
    response = client.post(
        "/auth/register", json={"email": "C@example.test", "name": "C", "password": PASSWORD}
    )
    assert response.status_code == 409


def test_mauvais_mot_de_passe(client):
    register(client, "d@example.test")
    response = client.post("/auth/login", json={"email": "d@example.test", "password": "mauvais-mot"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer jeton-invalide"}, {"Authorization": "Basic abc"}],
)
def test_jeton_invalide(client, headers):
    assert client.get("/me", headers=headers).status_code == 401


def test_jeton_signe_avec_un_autre_secret(client, settings):
    from stochastiq_api.security import create_token

    forged = create_token(1, "un-autre-secret-de-plus-de-32-caracteres", 12)
    assert client.get("/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_champ_inconnu_refuse(client):
    response = client.post(
        "/auth/register",
        json={"email": "e@example.test", "name": "E", "password": PASSWORD, "is_admin": True},
    )
    assert response.status_code == 422


def test_secret_par_defaut_refuse_hors_dev(tmp_path):
    settings = Settings(env="prod", secret_key=DEFAULT_SECRET_KEY, database_url=f"sqlite:///{tmp_path}/x.db")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(settings)


def test_secret_par_defaut_accepte_en_dev(tmp_path):
    create_app(Settings(env="dev", database_url=f"sqlite:///{tmp_path}/x.db"))


def test_cors_limite_a_l_origine_du_front(client):
    allowed = client.options(
        "/projects",
        headers={"Origin": "http://front.test", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://front.test"
    refused = client.options(
        "/projects",
        headers={"Origin": "http://malveillant.test", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in refused.headers


def test_jetons_d_invitation_masques_dans_les_journaux():
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "POST", "/invitations/AbC123-secret/accept", "1.1", 200), None,
    )
    MaskInvitationTokens().filter(record)
    assert "AbC123-secret" not in record.getMessage()
    assert "/invitations/***/accept" in record.getMessage()


def test_sante(client):
    assert client.get("/health").json()["status"] == "ok"


def test_espaces_du_mot_de_passe_conserves(client):
    password = "  espaces autour  "
    client.post("/auth/register", json={"email": "f@example.test", "name": " Fanny ", "password": password})
    assert client.post("/auth/login", json={"email": "f@example.test", "password": password}).status_code == 200
    stripped = password.strip()
    assert client.post("/auth/login", json={"email": "f@example.test", "password": stripped}).status_code == 401


def test_mot_de_passe_hache_en_argon2(client):
    from sqlalchemy import select

    from stochastiq_api.models import User

    register(client, "g@example.test")
    with client.app.state.sessionmaker() as session:
        stored = session.scalar(select(User).where(User.email == "g@example.test")).password_hash
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
