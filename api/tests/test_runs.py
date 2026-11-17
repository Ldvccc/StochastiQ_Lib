import time

import pytest
from fastapi.testclient import TestClient

from conftest import create_project, register
from stochastiq_api.jobs import MP_CONTEXT, ORPHAN_MESSAGE, format_duration
from stochastiq_api.main import create_app
from stochastiq_api.models import Run

SMALL = {
    "diagnostic": {"ansatz": "hardware_efficient", "n_qubits": 2, "layers": 1, "n_samples": 50, "seed": 0},
    "compare": {
        "ansatz": ["hardware_efficient", "rotation_only"],
        "n_qubits": 2,
        "layers": 1,
        "n_samples": 50,
        "n_seeds": 1,
        "seed": 0,
    },
    "scaling": {"ansatz": ["hardware_efficient"], "qubit_min": 2, "qubit_max": 3, "n_samples": 50, "seed": 0},
    "hardware": {"ansatz": "data_reuploading", "n_qubits": 2, "layers": 1, "topology": "line", "seed": 0},
}


def launch(client, headers, project_id, kind, params):
    return client.post(f"/projects/{project_id}/runs", json={"kind": kind, "params": params}, headers=headers)


def wait_run(client, headers, project_id, run_id, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/projects/{project_id}/runs/{run_id}", headers=headers).json()
        if run["status"] in ("done", "failed"):
            return run
        time.sleep(0.5)
    raise AssertionError(f"run {run_id} toujours en cours après {timeout} s")


@pytest.fixture
def owner_project(client):
    owner = register(client)
    return owner, create_project(client, owner)


@pytest.mark.parametrize("kind", list(SMALL))
def test_cycle_de_vie_d_un_run(client, owner_project, kind):
    owner, project_id = owner_project
    response = launch(client, owner, project_id, kind, SMALL[kind])
    assert response.status_code == 202, response.text
    created = response.json()
    assert created["status"] == "pending"
    assert created["result"] is None

    run = wait_run(client, owner, project_id, created["id"])
    assert run["status"] == "done", run["error"]
    assert run["error"] is None
    assert run["started_at"] and run["finished_at"]
    result = run["result"]
    if kind == "diagnostic":
        assert set(result) == {"expressibility", "entangling_capability", "gradient", "stats", "histogram", "noise"}
        assert result["noise"] is None  # sans noise_profile
        assert set(result["histogram"]) == {"edges", "circuit", "haar"}
        assert set(result["gradient"]) >= {"mean_variance", "active_mean_variance", "inactive_fraction"}
        assert result["stats"]["n_qubits"] == 2
    elif kind == "compare":
        assert [row["ansatz"] for row in result["rows"]] == ["hardware_efficient", "rotation_only"]
        assert all(isinstance(row["pareto"], bool) for row in result["rows"])
        assert "gradient_variance_active" in result["rows"][0]
    elif kind == "scaling":
        (series,) = result["series"]
        assert series["observable"] == "Z0"
        assert [row["n_qubits"] for row in series["rows"]] == [2, 3]
        assert series["fit_active"]["factor_per_qubit"] is None  # 2 points seulement
    else:
        assert result["topology"] == "line"
        assert {"before", "basis_only", "after", "routing_overhead_two_qubit"} <= set(result)

    types = [e["type"] for e in client.get(f"/projects/{project_id}/activity", headers=owner).json()["items"]]
    assert types[:2] == ["run_done", "run_launched"]


def test_scaling_local_et_global(client, owner_project):
    owner, project_id = owner_project
    params = {**SMALL["scaling"], "compare_observables": True}
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "scaling", params).json()["id"])
    assert [s["observable"] for s in run["result"]["series"]] == ["Z0", "Zall"]


@pytest.mark.parametrize(
    "kind, change",
    [
        ("diagnostic", {"n_qubits": 1}),
        ("diagnostic", {"n_qubits": 9}),
        ("diagnostic", {"layers": 0}),
        ("diagnostic", {"layers": 9}),
        ("diagnostic", {"n_samples": 49}),
        ("diagnostic", {"n_samples": 5001}),
        ("diagnostic", {"ansatz": "inconnu"}),
        ("diagnostic", {"observable": "Z1"}),
        ("diagnostic", {"seed": -1}),
        ("diagnostic", {"inattendu": 1}),
        ("compare", {"n_seeds": 0}),
        ("compare", {"n_seeds": 11}),
        ("compare", {"ansatz": []}),
        ("compare", {"ansatz": ["rotation_only", "rotation_only"]}),
        ("scaling", {"ansatz": ["hardware_efficient", "rotation_only", "brick_wall", "all_to_all", "basic_entangler"]}),
        ("scaling", {"qubit_min": 5, "qubit_max": 3}),
        ("scaling", {"layers_mode": "quadratique"}),
        ("hardware", {"topology": "etoile"}),
    ],
)
def test_parametres_hors_limites_refuses(client, owner_project, kind, change):
    owner, project_id = owner_project
    response = launch(client, owner, project_id, kind, {**SMALL[kind], **change})
    assert response.status_code == 422
    assert client.get(f"/projects/{project_id}/runs", headers=owner).json()["total"] == 0


def test_type_de_run_inconnu(client, owner_project):
    owner, project_id = owner_project
    assert launch(client, owner, project_id, "entrainement", {}).status_code == 422


def test_deux_runs_simultanes_par_utilisateur(client, owner_project):
    owner, project_id = owner_project
    user_id = client.get("/me", headers=owner).json()["id"]
    with client.app.state.sessionmaker() as db:
        for status in ("pending", "running"):
            db.add(Run(project_id=project_id, created_by=user_id, kind="diagnostic", params={}, status=status))
        db.commit()
    response = launch(client, owner, project_id, "diagnostic", SMALL["diagnostic"])
    assert response.status_code == 429


def test_duree_maximale_depassee(settings):
    settings.run_timeout_seconds = 0.5
    with TestClient(create_app(settings)) as client:
        owner = register(client)
        project_id = create_project(client, owner)
        run_id = launch(client, owner, project_id, "diagnostic", {**SMALL["diagnostic"], "n_samples": 5000}).json()["id"]
        run = wait_run(client, owner, project_id, run_id, timeout=60)
    assert run["status"] == "failed"
    # Message construit à partir de run_timeout_seconds, en notation française.
    assert run["error"] == "Durée maximale dépassée (0,5 seconde)."


@pytest.mark.parametrize(
    "seconds, text",
    [(0.5, "0,5 seconde"), (1, "1 seconde"), (30, "30 secondes"), (60, "1 minute"), (90, "1,5 minute"), (600, "10 minutes")],
)
def test_format_de_la_duree(seconds, text):
    assert format_duration(seconds) == text


def test_orphelins_au_demarrage(settings):
    with TestClient(create_app(settings)) as client:
        owner = register(client)
        project_id = create_project(client, owner)
        with client.app.state.sessionmaker() as db:
            for status in ("pending", "running", "done"):
                db.add(Run(project_id=project_id, kind="diagnostic", params={}, status=status))
            db.commit()
    # Redémarrage de l'API sur la même base.
    with TestClient(create_app(settings)) as client:
        with client.app.state.sessionmaker() as db:
            runs = {run.id: (run.status, run.error) for run in db.query(Run).all()}
    assert runs[1] == ("failed", ORPHAN_MESSAGE)
    assert runs[2] == ("failed", ORPHAN_MESSAGE)
    assert runs[3] == ("done", None)


def test_liste_filtres_et_pagination(client, owner_project):
    owner, project_id = owner_project
    with client.app.state.sessionmaker() as db:
        for i in range(5):
            db.add(Run(project_id=project_id, kind="hardware" if i % 2 else "diagnostic", params={}, status="done"))
        db.add(Run(project_id=project_id, kind="compare", params={}, status="failed"))
        db.commit()
    page = client.get(f"/projects/{project_id}/runs?limit=2&offset=1", headers=owner).json()
    assert page["total"] == 6
    assert [run["id"] for run in page["items"]] == [5, 4]
    assert "result" not in page["items"][0]
    failed = client.get(f"/projects/{project_id}/runs?status=failed", headers=owner).json()
    assert [run["kind"] for run in failed["items"]] == ["compare"]
    hardware = client.get(f"/projects/{project_id}/runs?kind=hardware", headers=owner).json()
    assert hardware["total"] == 2
    assert client.get(f"/projects/{project_id}/runs?status=perdu", headers=owner).status_code == 422


def test_isolation_des_runs(client, owner_project):
    owner, project_id = owner_project
    other = register(client)
    other_project = create_project(client, other)
    with client.app.state.sessionmaker() as db:
        db.add(Run(project_id=project_id, kind="diagnostic", params={}, status="done"))
        db.commit()
    assert client.get(f"/projects/{project_id}/runs/1", headers=other).status_code == 404
    assert client.get(f"/projects/{other_project}/runs/1", headers=other).status_code == 404
    assert client.post(
        f"/projects/{other_project}/runs/1/comments", json={"text": "intrusion"}, headers=other
    ).status_code == 404
    assert launch(client, other, project_id, "diagnostic", SMALL["diagnostic"]).status_code == 404


def test_processus_de_calcul_crees_par_spawn():
    # « fork » bloque un routage Qiskit dans l'enfant après une transpilation dans le parent (Linux, Docker).
    assert MP_CONTEXT.get_start_method() == "spawn"
