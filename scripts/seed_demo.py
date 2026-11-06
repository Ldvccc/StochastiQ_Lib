"""Données de démonstration du prototype StochastiQ (compatible Windows).

Crée 4 utilisateurs fictifs, un projet « Démo universitaire » avec les
4 rôles, quelques runs réels de petite taille, des commentaires et des
circuits épinglés. Les opérations passent par l'API elle-même (en
processus, avec un vrai ordonnanceur de runs), sur la base indiquée par
DATABASE_URL (ou par ``--database-url``).

Utilisation, depuis la racine du dépôt (PowerShell) :

    .venv\\Scripts\\python scripts\\seed_demo.py
    .venv\\Scripts\\python scripts\\seed_demo.py --database-url sqlite:///./demo.db
"""

import argparse
import sys
import time

from fastapi.testclient import TestClient

from stochastiq_api.config import Settings
from stochastiq_api.main import create_app

DEMO_PASSWORD = "demo-stochastiq-2026"
PROJECT_NAME = "Démo universitaire"

# (nom, e-mail, rôle, titre). Le titre est une étiquette sans effet sur les droits.
MEMBERS = [
    ("[Membre 1]", "membre1@example.test", "owner", "CEO"),
    ("[Membre 2]", "membre2@example.test", "key_manager", "CTO"),
    ("[Membre 3]", "membre3@example.test", "editor", "Chercheur"),
    ("[Membre 4]", "membre4@example.test", "viewer", "Stagiaire"),
]

RUNS = [
    ("diagnostic", {"ansatz": "hardware_efficient", "n_qubits": 3, "layers": 2, "n_samples": 300, "seed": 0, "observable": "Z0"}),
    (
        "compare",
        {
            "ansatz": ["hardware_efficient", "strongly_entangling", "data_reuploading"],
            "n_qubits": 3,
            "layers": 2,
            "n_samples": 300,
            "n_seeds": 2,
            "seed": 0,
        },
    ),
    (
        "scaling",
        {
            "ansatz": ["hardware_efficient", "data_reuploading"],
            "qubit_min": 2,
            "qubit_max": 4,
            "layers": 2,
            "layers_mode": "fixed",
            "n_samples": 50,
            "compare_observables": True,
            "seed": 0,
        },
    ),
    ("hardware", {"ansatz": "data_reuploading", "n_qubits": 4, "layers": 3, "topology": "heavy_hex", "seed": 0}),
]

COMMENTS = [
    (0, 1, "Expressibilité correcte pour 3 qubits ; à comparer avec plus d'échantillons."),
    (1, 2, "Les écarts entre les trois ansatz restent proches du bruit avec 2 graines."),
    (2, 3, "La décroissance en coût global est nette pour les deux circuits."),
]


def check(response, expected: int = 200):
    if response.status_code != expected:
        sys.exit(f"Échec ({response.status_code}) : {response.text}")
    return response.json() if response.content else None


def login(client: TestClient, email: str) -> dict:
    token = check(client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD}))["access_token"]
    return {"Authorization": f"Bearer {token}"}


def wait(client: TestClient, headers: dict, project_id: int, run_id: int, timeout: float = 600) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = check(client.get(f"/projects/{project_id}/runs/{run_id}", headers=headers))
        if run["status"] in ("done", "failed"):
            return run
        time.sleep(1)
    sys.exit(f"Le run {run_id} n'est pas terminé après {timeout:.0f} s.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", help="base SQLAlchemy (par défaut : DATABASE_URL ou .env)")
    args = parser.parse_args()
    settings = Settings(**({"database_url": args.database_url} if args.database_url else {}))
    print(f"Base : {settings.database_url}")

    with TestClient(create_app(settings)) as client:
        first = MEMBERS[0][1]
        if client.post("/auth/login", json={"email": first, "password": DEMO_PASSWORD}).status_code == 200:
            sys.exit("Les comptes de démonstration existent déjà dans cette base : rien n'a été modifié.")

        for name, email, _, _ in MEMBERS:
            check(client.post("/auth/register", json={"email": email, "name": name, "password": DEMO_PASSWORD}), 201)
        headers = [login(client, email) for _, email, _, _ in MEMBERS]
        owner = headers[0]

        project = check(
            client.post(
                "/projects",
                json={"name": PROJECT_NAME, "description": "Projet fictif de démonstration du prototype StochastiQ."},
                headers=owner,
            ),
            201,
        )
        project_id = project["id"]
        ids = [check(client.get("/me", headers=h))["id"] for h in headers]
        for (name, email, role, title), member_headers, user_id in zip(MEMBERS, headers, ids):
            if role != "owner":
                invitation = check(
                    client.post(f"/projects/{project_id}/invitations", json={"email": email, "role": role}, headers=owner), 201
                )
                token = invitation["link"].rsplit("/", 1)[1]
                check(client.post(f"/invitations/{token}/accept", headers=member_headers))
            check(client.patch(f"/projects/{project_id}/members/{user_id}", json={"title": title}, headers=owner))

        # Runs lancés par l'éditeur ([Membre 3]) et le propriétaire, 2 au plus en même temps chacun.
        runs = []
        for index, (kind, params) in enumerate(RUNS):
            launcher = headers[2] if index % 2 == 0 else owner
            created = check(client.post(f"/projects/{project_id}/runs", json={"kind": kind, "params": params}, headers=launcher), 202)
            print(f"Run {created['id']} ({kind}) lancé, calcul en cours...")
            run = wait(client, launcher, project_id, created["id"])
            print(f"Run {run['id']} ({kind}) : {run['status']}")
            runs.append(run)

        for run_index, member_index, text in COMMENTS:
            check(
                client.post(f"/projects/{project_id}/runs/{runs[run_index]['id']}/comments", json={"text": text}, headers=headers[member_index]),
                201,
            )
        for ansatz, n_qubits, layers in [("hardware_efficient", 3, 2), ("data_reuploading", 4, 3)]:
            check(client.post(f"/projects/{project_id}/pins", json={"ansatz": ansatz, "n_qubits": n_qubits, "layers": layers}, headers=headers[2]), 201)
        check(client.post(f"/projects/{project_id}/machines", json={"provider": "IBM", "label": "Machine de démonstration (sans clé)"}, headers=headers[1]), 201)

    print()
    print(f"Projet « {PROJECT_NAME} » créé (n° {project_id}).")
    print(f"Mot de passe de démonstration de tous les comptes : {DEMO_PASSWORD}")
    for name, email, role, title in MEMBERS:
        print(f"  {name:<11} {email:<24} rôle {role:<12} titre {title}")


if __name__ == "__main__":
    main()
