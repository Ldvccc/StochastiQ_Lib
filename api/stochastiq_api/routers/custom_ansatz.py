"""Ansatz personnalisés du client : spec JSON ou OpenQASM 3, validés à l'enregistrement."""

import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from stochastiq import build_from_spec, circuit_stats, circuit_structure, load_qasm, spec_qubits, validate_ansatz, validate_spec
from stochastiq.custom_ansatz import MAX_QASM_CHARS

from ..db import get_db
from ..deps import ProjectAccess, require_role
from ..models import CustomAnsatz
from ..roles import MIN_ROLE
from ..schemas import Input, Name

router = APIRouter(tags=["ansatz personnalisés"])

# Couches utilisées pour valider une spec à l'enregistrement.
VALIDATION_LAYERS = 1


class CustomAnsatzIn(Input):
    name: Name
    format: Literal["spec", "qasm"]
    spec: dict[str, Any] | None = None
    qasm: str | None = Field(default=None, max_length=MAX_QASM_CHARS)

    @model_validator(mode="after")
    def _one_content(self) -> "CustomAnsatzIn":
        if self.format == "spec" and (self.spec is None or self.qasm is not None):
            raise ValueError("Le format « spec » demande le champ spec (et pas qasm).")
        if self.format == "qasm" and (self.qasm is None or self.spec is not None):
            raise ValueError("Le format « qasm » demande le champ qasm (et pas spec).")
        return self


class CustomAnsatzPatch(Input):
    name: Name


class CustomAnsatzOut(BaseModel):
    id: int
    name: str
    format: Literal["spec", "qasm"]
    content: str
    spec: dict[str, Any] | None
    n_qubits: int | None
    created_by: int | None
    created_at: datetime


def check_content(format: str, spec: dict | None, qasm: str | None) -> tuple[str, int | None]:
    """Valide un ansatz client ; retourne (contenu normalisé, nombre de qubits fixé ou None)."""
    if format == "spec":
        normalized = validate_spec(spec)
        fixed = spec_qubits(normalized)
        for n_qubits in [fixed] if fixed is not None else [2, 8]:
            validate_ansatz(build_from_spec(normalized, n_qubits, VALIDATION_LAYERS))
        return json.dumps(normalized, sort_keys=True), fixed
    qc = validate_ansatz(load_qasm(qasm))
    return qasm, qc.num_qubits


def build_circuit(format: str, content: str, n_qubits: int, layers: int):
    """Circuit d'un ansatz client, validé (le QASM ignore n_qubits et layers)."""
    if format == "spec":
        return validate_ansatz(build_from_spec(json.loads(content), n_qubits, layers))
    return validate_ansatz(load_qasm(content))


def _out(ansatz: CustomAnsatz) -> CustomAnsatzOut:
    return CustomAnsatzOut(
        id=ansatz.id,
        name=ansatz.name,
        format=ansatz.format,
        content=ansatz.content,
        spec=json.loads(ansatz.content) if ansatz.format == "spec" else None,
        n_qubits=ansatz.n_qubits,
        created_by=ansatz.created_by,
        created_at=ansatz.created_at,
    )


def get_custom(db: Session, project_id: int, ansatz_id: int) -> CustomAnsatz:
    ansatz = db.get(CustomAnsatz, ansatz_id)
    if ansatz is None or ansatz.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ansatz personnalisé introuvable.")
    return ansatz


@router.get("/projects/{project_id}/custom-ansatz", response_model=list[CustomAnsatzOut])
def list_custom(
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])), db: Session = Depends(get_db)
) -> list[CustomAnsatzOut]:
    rows = db.scalars(
        select(CustomAnsatz).where(CustomAnsatz.project_id == access.project.id).order_by(CustomAnsatz.id)
    ).all()
    return [_out(a) for a in rows]


@router.post("/projects/{project_id}/custom-ansatz", response_model=CustomAnsatzOut, status_code=status.HTTP_201_CREATED)
def create_custom(
    data: CustomAnsatzIn,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["custom_ansatz"])),
    db: Session = Depends(get_db),
) -> CustomAnsatzOut:
    try:
        content, n_qubits = check_content(data.format, data.spec, data.qasm)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    ansatz = CustomAnsatz(
        project_id=access.project.id,
        name=data.name,
        format=data.format,
        content=content,
        n_qubits=n_qubits,
        created_by=access.user.id,
    )
    db.add(ansatz)
    db.commit()
    return _out(ansatz)


@router.get("/projects/{project_id}/custom-ansatz/{ansatz_id}", response_model=CustomAnsatzOut)
def get_one(
    ansatz_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> CustomAnsatzOut:
    return _out(get_custom(db, access.project.id, ansatz_id))


@router.get("/projects/{project_id}/custom-ansatz/{ansatz_id}/structure")
def structure(
    ansatz_id: int,
    n_qubits: int = Query(default=4, ge=2, le=8),
    layers: int = Query(default=2, ge=1, le=8),
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> dict:
    """Aperçu : structure (``circuit_structure``) et statistiques. Le QASM et la spec « custom » imposent leur n."""
    ansatz = get_custom(db, access.project.id, ansatz_id)
    n_qubits = ansatz.n_qubits or n_qubits
    try:
        qc = build_circuit(ansatz.format, ansatz.content, n_qubits, layers)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {**circuit_structure(qc), "layers": layers if ansatz.format == "spec" else None, "stats": circuit_stats(qc)}


@router.patch("/projects/{project_id}/custom-ansatz/{ansatz_id}", response_model=CustomAnsatzOut)
def rename(
    ansatz_id: int,
    data: CustomAnsatzPatch,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["custom_ansatz"])),
    db: Session = Depends(get_db),
) -> CustomAnsatzOut:
    ansatz = get_custom(db, access.project.id, ansatz_id)
    ansatz.name = data.name
    db.commit()
    return _out(ansatz)


@router.delete("/projects/{project_id}/custom-ansatz/{ansatz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    ansatz_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["custom_ansatz"])),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(get_custom(db, access.project.id, ansatz_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
