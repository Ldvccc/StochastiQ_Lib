import json

import pytest

from conftest import create_project, register
from stochastiq_api.roles import ROLES, has_role
from test_runs import launch, wait_run

SPEC = {"rotations": ["ry", "rz"], "entangler": "linear"}
PAIRS = {"rotations": ["ry"], "entangler": "custom", "pairs": [[0, 1], [1, 2]]}
QASM3 = """OPENQASM 3.0;
include "stdgates.inc";
input float[64] a;
input float[64] b;
input float[64] c;
qubit[3] q;
ry(a) q[0];
ry(b) q[1];
rz(c) q[2];
cx q[0], q[1];
cx q[1], q[2];
"""
QASM2 = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nry(0.3) q[0];\ncx q[0],q[1];\n'


def _create(client, headers, project_id, **body):
    return client.post(f"/projects/{project_id}/custom-ansatz", json={"name": "Mon ansatz", **body}, headers=headers)


@pytest.fixture
def owner_project(client):
    owner = register(client)
    return owner, create_project(client, owner)


def test_spec_normalisee(client, owner_project):
    owner, project_id = owner_project
    created = _create(client, owner, project_id, format="spec", spec={"entangler": "linear", "rotations": ["ry", "rz"]})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["n_qubits"] is None
    assert body["spec"] == SPEC
    assert body["content"] == json.dumps(SPEC, sort_keys=True)


def test_spec_custom_et_qasm3_fixent_n(client, owner_project):
    owner, project_id = owner_project
    assert _create(client, owner, project_id, format="spec", spec=PAIRS).json()["n_qubits"] == 3
    qasm = _create(client, owner, project_id, format="qasm", qasm=QASM3).json()
    assert qasm["n_qubits"] == 3
    assert qasm["spec"] is None


@pytest.mark.parametrize(
    "body, message",
    [
        ({"format": "qasm", "qasm": QASM2}, "OpenQASM 2 ne permet pas de paramètres"),
        ({"format": "spec", "spec": {"rotations": ["u3"], "entangler": "ring"}}, "Rotation inconnue"),
        ({"format": "spec", "spec": {"rotations": ["ry"], "entangler": "ring", "code": "import os"}}, "Clé(s) inconnue(s)"),
        ({"format": "spec", "qasm": QASM3}, "demande le champ spec"),
        ({"format": "qasm", "qasm": "OPENQASM 3.0;\nqubit[2] q;\nmeasure q;"}, "OpenQASM"),
        ({"format": "qasm", "qasm": "x" * 20_001}, "20000"),
    ],
)
def test_refus_a_l_enregistrement(client, owner_project, body, message):
    owner, project_id = owner_project
    response = _create(client, owner, project_id, **body)
    assert response.status_code == 422
    assert message in response.text


def test_apercu_de_structure(client, owner_project):
    owner, project_id = owner_project
    spec_id = _create(client, owner, project_id, format="spec", spec=SPEC).json()["id"]
    preview = client.get(f"/projects/{project_id}/custom-ansatz/{spec_id}/structure?n_qubits=3&layers=2", headers=owner).json()
    assert preview["n_qubits"] == 3
    assert preview["stats"]["gate_counts"] == {"ry": 6, "rz": 6, "cx": 4}
    qasm_id = _create(client, owner, project_id, format="qasm", qasm=QASM3).json()["id"]
    preview = client.get(f"/projects/{project_id}/custom-ansatz/{qasm_id}/structure?n_qubits=6", headers=owner).json()
    assert preview["n_qubits"] == 3  # le QASM impose son nombre de qubits
    assert preview["layers"] is None


@pytest.mark.parametrize("role", [*ROLES, "outsider"])
def test_droits(client, team, role):
    headers, project_id = team["headers"][role], team["project_id"]
    existing = _create(client, team["headers"]["owner"], project_id, format="spec", spec=SPEC).json()["id"]
    read = client.get(f"/projects/{project_id}/custom-ansatz/{existing}", headers=headers)
    create = _create(client, headers, project_id, format="spec", spec=SPEC)
    delete = client.delete(f"/projects/{project_id}/custom-ansatz/{existing}", headers=headers)
    if role == "outsider":
        assert {read.status_code, create.status_code, delete.status_code} == {404}
    else:
        assert read.status_code == 200
        assert create.status_code == (201 if has_role(role, "editor") else 403)
        assert delete.status_code == (204 if has_role(role, "editor") else 403)


def test_run_avec_un_ansatz_personnalise_reproductible(client, owner_project):
    owner, project_id = owner_project
    ansatz_id = _create(client, owner, project_id, format="spec", spec=SPEC).json()["id"]
    params = {"ansatz": {"custom_id": ansatz_id}, "n_qubits": 2, "layers": 1, "n_samples": 50, "seed": 0}
    created = launch(client, owner, project_id, "diagnostic", params)
    assert created.status_code == 202, created.text
    stored = created.json()["params"]["ansatz"]
    assert stored == {"custom": {"id": ansatz_id, "name": "Mon ansatz", "format": "spec", "content": json.dumps(SPEC, sort_keys=True), "n_qubits": None}}
    # Supprimer l'ansatz n'empêche pas le run de s'exécuter : il embarque la spec.
    client.delete(f"/projects/{project_id}/custom-ansatz/{ansatz_id}", headers=owner)
    run = wait_run(client, owner, project_id, created.json()["id"])
    assert run["status"] == "done", run["error"]
    assert run["result"]["stats"]["gate_counts"] == {"ry": 2, "rz": 2, "cx": 1}


def test_comparaison_catalogue_et_qasm(client, owner_project):
    owner, project_id = owner_project
    ansatz_id = _create(client, owner, project_id, name="Circuit QASM", format="qasm", qasm=QASM3).json()["id"]
    params = {"ansatz": ["hardware_efficient", {"custom_id": ansatz_id}], "n_qubits": 3, "layers": 1, "n_samples": 50, "n_seeds": 1, "seed": 0}
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "compare", params).json()["id"])
    assert run["status"] == "done", run["error"]
    assert sorted(row["ansatz"] for row in run["result"]["rows"]) == ["Circuit QASM", "hardware_efficient"]


def test_materiel_avec_un_qasm(client, owner_project):
    owner, project_id = owner_project
    ansatz_id = _create(client, owner, project_id, format="qasm", qasm=QASM3).json()["id"]
    params = {"ansatz": {"custom_id": ansatz_id}, "n_qubits": 3, "layers": 1, "topology": "line", "seed": 0}
    run = wait_run(client, owner, project_id, launch(client, owner, project_id, "hardware", params).json()["id"])
    assert run["status"] == "done", run["error"]
    assert run["result"]["before"]["n_two_qubit_gates"] == 2


def test_refus_au_lancement(client, owner_project):
    owner, project_id = owner_project
    fixed = _create(client, owner, project_id, format="spec", spec=PAIRS).json()["id"]
    mismatch = launch(client, owner, project_id, "diagnostic", {"ansatz": {"custom_id": fixed}, "n_qubits": 4, "layers": 1, "n_samples": 50})
    assert mismatch.status_code == 422
    assert "fixe 3 qubits, mais le run en demande 4" in mismatch.text
    scaling = launch(client, owner, project_id, "scaling", {"ansatz": [{"custom_id": fixed}], "qubit_min": 2, "qubit_max": 3, "n_samples": 50})
    assert scaling.status_code == 422
    assert "paramétrable en nombre de qubits" in scaling.text
    other = register(client)
    other_project = create_project(client, other)
    foreign = _create(client, other, other_project, format="spec", spec=SPEC).json()["id"]
    response = launch(client, owner, project_id, "diagnostic", {"ansatz": {"custom_id": foreign}, "n_qubits": 2, "layers": 1, "n_samples": 50})
    assert response.status_code == 422
    assert "introuvable dans ce projet" in response.text
    duplicate = launch(
        client, owner, project_id, "compare",
        {"ansatz": [{"custom_id": fixed}, {"custom_id": fixed}], "n_qubits": 3, "layers": 1, "n_samples": 50},
    )
    assert duplicate.status_code == 422
    assert client.get(f"/projects/{project_id}/runs", headers=owner).json()["total"] == 0


def test_isolation(client, owner_project):
    owner, project_id = owner_project
    ansatz_id = _create(client, owner, project_id, format="spec", spec=SPEC).json()["id"]
    other = register(client)
    other_project = create_project(client, other)
    assert client.get(f"/projects/{other_project}/custom-ansatz/{ansatz_id}", headers=other).status_code == 404
