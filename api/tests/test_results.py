import time

import pandas as pd
import pytest
from sqlalchemy import select

from conftest import create_project, register
from stochastiq_api.ml.results import eligible_query, export_results, fingerprint
from stochastiq_api.models import Result
from test_runs import SMALL, launch, wait_run
from test_training import PROBLEM


@pytest.fixture
def owner_project(client):
    owner = register(client)
    return owner, create_project(client, owner)


def run_and_rows(client, headers, project_id, kind, params, expected):
    """Lance un run, attend sa fin puis ses lignes (enregistrées juste après le passage à « done »)."""
    run = wait_run(client, headers, project_id, launch(client, headers, project_id, kind, params).json()["id"])
    assert run["status"] == "done", run["error"]
    deadline = time.monotonic() + 10
    while True:
        with client.app.state.sessionmaker() as db:
            rows = db.scalars(select(Result).where(Result.run_id == run["id"]).order_by(Result.id)).all()
        if len(rows) >= expected or time.monotonic() > deadline:
            return run, rows
        time.sleep(0.2)


def test_diagnostic_avec_bruit(client, owner_project):
    owner, project_id = owner_project
    params = {**SMALL["diagnostic"], "noise_profile": "moyen"}
    _, rows = run_and_rows(client, owner, project_id, "diagnostic", params, 2)
    assert [r.type for r in rows] == ["diagnostic", "noise"]
    diag, noise = rows
    assert diag.source == "run" and diag.project_id == project_id and diag.config_key is None
    assert diag.ansatz == "hardware_efficient" and diag.ansatz_fingerprint == "cat:hardware_efficient"
    assert diag.circuit_features["n_parameters"] == 4
    assert diag.problem_features is None and diag.noise_profile is None
    assert set(diag.quantities) >= {"expressibility", "entangling_capability", "gradient_mean_variance"}
    assert noise.noise_profile == {"p1": 1e-3, "p2": 5e-3, "readout": 1e-2}
    assert noise.noise_topology == "line"
    assert noise.quantities["n_samples"] == 20 and noise.quantities["n2"] >= 1
    assert diag.library_version


def test_entrainement_sous_bruit_sans_probabilites_brutes(client, owner_project):
    owner, project_id = owner_project
    problem = client.post(f"/projects/{project_id}/problems/csv", json=PROBLEM, headers=owner).json()
    params = {
        "problem_id": problem["id"], "ansatz": "hardware_efficient", "layers": 2, "max_iter": 20, "seed": 0,
        "evaluate_noise": {"profile": "fort", "topology": "ring"},
    }
    run, rows = run_and_rows(client, owner, project_id, "training", params, 2)
    assert run["params"]["problem_family"] == "csv"
    assert [r.type for r in rows] == ["training", "training_noise"]
    training, noisy = rows
    assert training.problem_family == "csv"
    assert set(training.problem_features) >= {"entropy", "mean_mutual_information"}
    assert training.quantities["tvd"] == pytest.approx(run["result"]["metrics"]["tvd"])
    assert training.quantities["best_baseline_tvd"] == pytest.approx(0.0, abs=1e-9)  # cible à structure d'arbre
    assert noisy.noise_topology == "ring"
    assert noisy.quantities["degradation"] == pytest.approx(noisy.quantities["tvd_noisy"] - noisy.quantities["tvd_exact"])
    # Jamais le vecteur de probabilités du client : uniquement des valeurs scalaires.
    for row in rows:
        for values in (row.circuit_features, row.problem_features, row.noise_profile or {}, row.quantities):
            assert all(not isinstance(value, (list, dict)) for value in values.values()), values


def test_famille_d_un_probleme_de_reference(client, owner_project):
    owner, project_id = owner_project
    body = {"name": "Gauss", "reference": {"distribution": "gaussian", "n_qubits": 2}}
    problem = client.post(f"/projects/{project_id}/problems", json=body, headers=owner).json()
    params = {"problem_id": problem["id"], "ansatz": "rotation_only", "layers": 1, "max_iter": 10, "seed": 0}
    _, rows = run_and_rows(client, owner, project_id, "training", params, 1)
    assert rows[0].problem_family == "gaussian"


def test_runs_sans_ligne(client, owner_project):
    owner, project_id = owner_project
    for kind in ("compare", "hardware"):
        _, rows = run_and_rows(client, owner, project_id, kind, SMALL[kind], 0)
        assert rows == []


def test_empreinte_d_un_ansatz_personnalise(client, owner_project):
    owner, project_id = owner_project
    body = {"name": "Mon RY", "format": "spec", "spec": {"rotations": ["ry"], "entangler": "linear"}}
    custom = client.post(f"/projects/{project_id}/custom-ansatz", json=body, headers=owner).json()
    params = {"ansatz": {"custom_id": custom["id"]}, "n_qubits": 3, "layers": 1, "profile": "faible", "n_samples": 2}
    run, rows = run_and_rows(client, owner, project_id, "noise", params, 1)
    assert rows[0].ansatz == "Mon RY"
    assert rows[0].ansatz_fingerprint == fingerprint(run["params"]["ansatz"])
    assert rows[0].ansatz_fingerprint.startswith("custom:") and len(rows[0].ansatz_fingerprint) == 23


def test_partage_des_resultats(client, team):
    project_id, headers = team["project_id"], team["headers"]
    assert client.get(f"/projects/{project_id}", headers=headers["owner"]).json()["share_results"] is False
    response = client.patch(f"/projects/{project_id}", json={"share_results": True}, headers=headers["editor"])
    assert response.status_code == 403
    response = client.patch(f"/projects/{project_id}", json={"share_results": True}, headers=headers["owner"])
    assert response.status_code == 200 and response.json()["share_results"] is True


def test_lignes_eligibles_et_export(client, tmp_path):
    owner = register(client)
    private = create_project(client, owner, "Privé")
    shared = create_project(client, owner, "Partagé")
    client.patch(f"/projects/{shared}", json={"share_results": True}, headers=owner)
    run_and_rows(client, owner, private, "diagnostic", SMALL["diagnostic"], 1)
    run_and_rows(client, owner, shared, "diagnostic", SMALL["diagnostic"], 1)
    with client.app.state.sessionmaker() as db:
        grid = Result(
            source="grid", type="diagnostic", config_key="grid|test", ansatz="rotation_only",
            ansatz_fingerprint="cat:rotation_only", n_qubits=2, layers=1, circuit_features={"n_qubits": 2},
            quantities={"expressibility": 1.0}, library_version="test",
        )
        db.add(grid)
        db.commit()
        eligible = db.scalars(eligible_query()).all()
        assert sorted((r.source, r.project_id) for r in eligible) == [("grid", None), ("run", shared)]
        assert export_results(db, tmp_path / "base.csv") == 2
        assert export_results(db, tmp_path / "toute.csv", eligible_only=False) == 3
        with pytest.raises(ValueError, match=r"\.csv ou \.parquet"):
            export_results(db, tmp_path / "base.xlsx")
    frame = pd.read_csv(tmp_path / "base.csv")
    assert {"circuit_n_qubits", "q_expressibility", "ansatz_fingerprint"} <= set(frame.columns)
