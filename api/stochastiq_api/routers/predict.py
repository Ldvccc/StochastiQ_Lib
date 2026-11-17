from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..ansatz_refs import resolve_params
from ..db import get_db
from ..deps import ProjectAccess, require_role
from ..ml.predictor import load_bundle
from ..ml.service import NO_MODEL, model_info, prediction
from ..models import Problem
from ..roles import MIN_ROLE
from ..run_schemas import AnsatzRef, Layers, NoiseProfile, NoiseTopology
from ..schemas import Input

router = APIRouter(tags=["prediction"])


class PredictIn(Input):
    problem_id: int
    ansatz: AnsatzRef
    layers: Layers
    noise_profile: NoiseProfile | None = None
    topology: NoiseTopology = "line"


def get_bundle(request: Request) -> dict:
    bundle = load_bundle(request.app.state.settings.models_dir)
    if bundle is None:
        raise HTTPException(409, NO_MODEL)
    return bundle


@router.post("/projects/{project_id}/predict")
def predict_route(
    data: PredictIn,
    request: Request,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["run"])),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """TVD finale prédite (et dégradation sous bruit), avec intervalle 10-90 % et références."""
    bundle = get_bundle(request)
    problem = db.get(Problem, data.problem_id)
    if problem is None or problem.project_id != access.project.id:
        raise HTTPException(422, f"Problème n° {data.problem_id} introuvable dans ce projet.")
    params = resolve_params(
        db, access.project.id, "predict", {"ansatz": data.model_dump()["ansatz"], "n_qubits": problem.n_qubits, "layers": data.layers}
    )
    profile = data.model_dump()["noise_profile"]
    family = problem.source_params.get("distribution") if problem.origin == "reference" else "csv"
    result = prediction(bundle, params["ansatz"], problem.n_qubits, data.layers, problem.features, family, profile, data.topology)
    return {**result, "n_qubits": problem.n_qubits, "model": model_info(bundle)}
