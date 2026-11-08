"""Problèmes du client : distributions cibles créées depuis une référence ou un CSV."""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from stochastiq import from_probabilities, from_samples, list_distributions, problem_features, reference_distribution

from ..db import get_db
from ..deps import ProjectAccess, require_role
from ..events import record
from ..models import Problem
from ..problem_import import MAX_CSV_BYTES, parse_probabilities, parse_samples
from ..roles import MIN_ROLE
from ..schemas import Input, Name

router = APIRouter(tags=["problèmes"])

DistributionName = Literal[tuple(list_distributions())]
Qubits = Annotated[int, Field(ge=2, le=8)]


class ReferenceIn(Input):
    distribution: DistributionName
    n_qubits: Qubits
    seed: Annotated[int, Field(ge=0, le=1_000_000)] | None = None


class ProblemReferenceIn(Input):
    name: Name
    reference: ReferenceIn


class ProblemCsvIn(Input):
    name: Name
    format: Literal["probabilities", "samples"]
    content: Annotated[str, Field(min_length=1, max_length=MAX_CSV_BYTES)]
    # Format « samples » seulement : qubits, un intervalle [min, max] par variable, encodage.
    n_qubits: Qubits | None = None
    ranges: Annotated[list[tuple[float, float]], Field(min_length=1, max_length=8)] | None = None
    encoding: Literal["binary", "gray"] = "binary"

    @model_validator(mode="after")
    def _samples_options(self) -> "ProblemCsvIn":
        if self.format == "samples" and (self.n_qubits is None or self.ranges is None):
            raise ValueError("Le format « samples » demande n_qubits et un intervalle par variable (ranges).")
        return self


class ProblemPatch(Input):
    name: Name


class ProblemSummary(BaseModel):
    id: int
    name: str
    n_qubits: int
    origin: Literal["reference", "csv"]
    source_params: dict[str, Any]
    features: dict[str, Any]
    created_by: int | None
    created_at: datetime


class ProblemOut(ProblemSummary):
    probabilities: list[float]


def _summary(problem: Problem) -> dict:
    return {
        "id": problem.id,
        "name": problem.name,
        "n_qubits": problem.n_qubits,
        "origin": problem.origin,
        "source_params": problem.source_params,
        "features": problem.features,
        "created_by": problem.created_by,
        "created_at": problem.created_at,
    }


def _create(db: Session, access: ProjectAccess, name: str, origin: str, probs, source_params: dict) -> ProblemOut:
    vector = [float(p) for p in probs]
    n_qubits = len(vector).bit_length() - 1
    problem = Problem(
        project_id=access.project.id,
        name=name,
        n_qubits=n_qubits,
        origin=origin,
        probabilities=vector,
        source_params=source_params,
        features=problem_features(vector),
        created_by=access.user.id,
    )
    db.add(problem)
    db.flush()
    record(
        db,
        access.project.id,
        access.user.id,
        "problem_added",
        {"problem_id": problem.id, "name": name, "n_qubits": n_qubits, "origin": origin},
    )
    db.commit()
    return ProblemOut(**_summary(problem), probabilities=vector)


def _invalid(error: ValueError) -> HTTPException:
    return HTTPException(422, str(error))


@router.get("/distributions")
def distributions() -> list[dict]:
    """Distributions de référence proposées pour créer un problème (route publique)."""
    labels = {
        "gaussian": "Gaussienne discrétisée",
        "bimodal": "Mélange bimodal",
        "lognormal": "Log-normale (finance)",
        "uniform": "Uniforme",
        "bars_and_stripes": "Bars-and-Stripes (4 ou 6 qubits)",
        "ising_boltzmann": "Boltzmann d'un modèle d'Ising aléatoire",
    }
    return [
        {
            "name": name,
            "label": labels[name],
            "random": name == "ising_boltzmann",
            "qubits": [4, 6] if name == "bars_and_stripes" else list(range(2, 9)),
        }
        for name in list_distributions()
    ]


@router.get("/projects/{project_id}/problems", response_model=list[ProblemSummary])
def list_problems(
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])), db: Session = Depends(get_db)
) -> list[ProblemSummary]:
    problems = db.scalars(
        select(Problem).where(Problem.project_id == access.project.id).order_by(Problem.id.desc())
    ).all()
    return [ProblemSummary(**_summary(p)) for p in problems]


@router.post("/projects/{project_id}/problems", response_model=ProblemOut, status_code=status.HTTP_201_CREATED)
def create_from_reference(
    data: ProblemReferenceIn,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["problems"])),
    db: Session = Depends(get_db),
) -> ProblemOut:
    """Crée un problème à partir d'une distribution de référence."""
    ref = data.reference
    try:
        probs = reference_distribution(ref.distribution, ref.n_qubits, seed=ref.seed)
    except ValueError as error:
        raise _invalid(error) from error
    return _create(db, access, data.name, "reference", probs, ref.model_dump())


@router.post("/projects/{project_id}/problems/csv", response_model=ProblemOut, status_code=status.HTTP_201_CREATED)
def create_from_csv(
    data: ProblemCsvIn,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["problems"])),
    db: Session = Depends(get_db),
) -> ProblemOut:
    """Crée un problème à partir d'un CSV (au plus 1 Mo et 100 000 lignes). Le contenu n'est pas conservé."""
    try:
        if data.format == "probabilities":
            mapping = parse_probabilities(data.content)
            probs = from_probabilities(mapping)
            params = {"format": "probabilities", "rows": len(mapping)}
        else:
            samples = parse_samples(data.content)
            probs = from_samples(samples, data.n_qubits, data.ranges, encoding=data.encoding)
            params = {
                "format": "samples",
                "rows": len(samples),
                "n_qubits": data.n_qubits,
                "ranges": [list(r) for r in data.ranges],
                "encoding": data.encoding,
            }
    except ValueError as error:
        raise _invalid(error) from error
    return _create(db, access, data.name, "csv", probs, params)


def _get(db: Session, project_id: int, problem_id: int) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or problem.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Problème introuvable.")
    return problem


@router.get("/projects/{project_id}/problems/{problem_id}", response_model=ProblemOut)
def get_problem(
    problem_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> ProblemOut:
    problem = _get(db, access.project.id, problem_id)
    return ProblemOut(**_summary(problem), probabilities=problem.probabilities)


@router.patch("/projects/{project_id}/problems/{problem_id}", response_model=ProblemSummary)
def rename_problem(
    problem_id: int,
    data: ProblemPatch,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["problems"])),
    db: Session = Depends(get_db),
) -> ProblemSummary:
    problem = _get(db, access.project.id, problem_id)
    problem.name = data.name
    db.commit()
    return ProblemSummary(**_summary(problem))


@router.delete("/projects/{project_id}/problems/{problem_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_problem(
    problem_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["problems"])),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(_get(db, access.project.id, problem_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
