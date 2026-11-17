import itertools
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from stochastiq_api import security
from stochastiq_api.config import Settings
from stochastiq_api.main import create_app

PASSWORD = "motdepasse-solide"
GRID = Path(__file__).resolve().parents[2] / "data" / "results_grid.csv"

_counter = itertools.count()


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    """Paramètres argon2 allégés, pour les tests seulement (l'API garde les valeurs par défaut)."""
    monkeypatch.setattr(security, "_hasher", PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1))


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        secret_key="secret-de-test-assez-long-pour-hs256-0123456789",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        cors_origin="http://front.test",
        # Dossier vide : les tests ne dépendent pas d'un modèle entraîné sur le poste.
        models_dir=str(tmp_path / "models"),
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def register(client: TestClient, email: str | None = None, name: str = "Utilisateur") -> dict:
    """Crée un compte et retourne les en-têtes d'authentification."""
    email = email or f"utilisateur{next(_counter)}@example.test"
    response = client.post("/auth/register", json={"email": email, "name": name, "password": PASSWORD})
    assert response.status_code == 201, response.text
    token = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_project(client: TestClient, headers: dict, name: str = "Projet de test") -> int:
    response = client.post("/projects", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_member(client: TestClient, owner: dict, project_id: int, role: str) -> tuple[dict, int]:
    """Invite un nouveau compte avec ``role`` et l'accepte ; retourne (en-têtes, id)."""
    email = f"membre{next(_counter)}@example.test"
    invitation = client.post(
        f"/projects/{project_id}/invitations", json={"email": email, "role": role}, headers=owner
    )
    assert invitation.status_code == 201, invitation.text
    headers = register(client, email)
    token = invitation.json()["link"].rsplit("/", 1)[1]
    assert client.post(f"/invitations/{token}/accept", headers=headers).status_code == 200
    return headers, client.get("/me", headers=headers).json()["id"]


@pytest.fixture
def team(client):
    """Projet avec un membre par rôle et un utilisateur extérieur au projet."""
    owner = register(client, name="Propriétaire")
    project_id = create_project(client, owner)
    members = {"owner": owner}
    ids = {"owner": client.get("/me", headers=owner).json()["id"]}
    for role in ("key_manager", "editor", "viewer"):
        members[role], ids[role] = add_member(client, owner, project_id, role)
    members["outsider"] = register(client, name="Extérieur")
    return {"project_id": project_id, "headers": members, "ids": ids}


@pytest.fixture(scope="session")
def bundle():
    """Modèle de prédiction entraîné sur un sous-ensemble de la grille réelle (1 couche) : rapide, mêmes colonnes."""
    import pandas as pd

    from stochastiq_api.ml.predictor import train_predictor

    frame = pd.read_csv(GRID)
    return train_predictor(frame[frame["layers"] == 1], "test")


@pytest.fixture
def model_client(settings, bundle, tmp_path):
    """Client dont MODELS_DIR contient le modèle ``bundle``."""
    from stochastiq_api.ml.predictor import save_bundle

    save_bundle(bundle, tmp_path / "models")
    with TestClient(create_app(settings)) as test_client:
        yield test_client
