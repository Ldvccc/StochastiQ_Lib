from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ansatz_refs import resolve_params
from ..db import get_db
from ..deps import ProjectAccess, require_role
from ..events import record
from ..ml.predictor import load_bundle
from ..ml.service import NO_MODEL
from ..models import Comment, Run
from ..roles import MIN_ROLE
from ..run_schemas import (
    CommentIn,
    CommentOut,
    RunIn,
    RunKind,
    RunOut,
    RunPage,
    RunStatus,
    RunSummary,
    UserRef,
)

router = APIRouter(tags=["runs"])

MAX_ACTIVE_RUNS_PER_USER = 2


def _summary(run: Run) -> dict:
    return {
        "id": run.id,
        "project_id": run.project_id,
        "kind": run.kind,
        "params": run.params,
        "status": run.status,
        "error": run.error,
        "created_by": run.created_by,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


@router.post("/projects/{project_id}/runs", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def launch_run(
    request: Request,
    data: RunIn = Body(...),
    access: ProjectAccess = Depends(require_role(MIN_ROLE["run"])),
    db: Session = Depends(get_db),
) -> RunOut:
    """Enregistre un run et le place en file d'attente (202) ; suivre son statut avec GET."""
    active = db.scalar(
        select(func.count()).where(
            Run.created_by == access.user.id, Run.status.in_(("pending", "running"))
        )
    )
    if active >= MAX_ACTIVE_RUNS_PER_USER:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"{MAX_ACTIVE_RUNS_PER_USER} runs au maximum en cours par utilisateur : attendez la fin d'un run.",
        )
    if data.kind == "recommendation" and load_bundle(request.app.state.settings.models_dir) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, NO_MODEL)
    params = resolve_params(db, access.project.id, data.kind, data.params.model_dump())
    run = Run(project_id=access.project.id, created_by=access.user.id, kind=data.kind, params=params)
    db.add(run)
    db.flush()
    record(db, run.project_id, access.user.id, "run_launched", {"run_id": run.id, "kind": run.kind})
    db.commit()
    request.app.state.runs.submit(run.id)
    return RunOut(**_summary(run), result=None)


@router.get("/projects/{project_id}/runs", response_model=RunPage)
def list_runs(
    status_filter: RunStatus | None = Query(default=None, alias="status"),
    kind: RunKind | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> RunPage:
    """Runs du projet, du plus récent au plus ancien, filtrables par statut et par type."""
    query = select(Run).where(Run.project_id == access.project.id)
    if status_filter is not None:
        query = query.where(Run.status == status_filter)
    if kind is not None:
        query = query.where(Run.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    runs = db.scalars(query.order_by(Run.id.desc()).limit(limit).offset(offset)).all()
    return RunPage(items=[RunSummary(**_summary(run)) for run in runs], total=total)


def _get_run(db: Session, project_id: int, run_id: int) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run introuvable.")
    return run


@router.get("/projects/{project_id}/runs/{run_id}", response_model=RunOut)
def get_run(
    run_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> RunOut:
    run = _get_run(db, access.project.id, run_id)
    return RunOut(**_summary(run), result=run.result)


def _comment_out(comment: Comment) -> CommentOut:
    user = UserRef(id=comment.user.id, name=comment.user.name) if comment.user else None
    return CommentOut(
        id=comment.id, run_id=comment.run_id, user=user, text=comment.text, created_at=comment.created_at
    )


@router.post(
    "/projects/{project_id}/runs/{run_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    run_id: int,
    data: CommentIn,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["comment"])),
    db: Session = Depends(get_db),
) -> CommentOut:
    run = _get_run(db, access.project.id, run_id)
    comment = Comment(run_id=run.id, user_id=access.user.id, text=data.text)
    db.add(comment)
    db.flush()
    record(
        db,
        run.project_id,
        access.user.id,
        "comment_added",
        {"run_id": run.id, "comment_id": comment.id, "excerpt": data.text[:120]},
    )
    db.commit()
    return _comment_out(comment)


@router.get("/projects/{project_id}/runs/{run_id}/comments", response_model=list[CommentOut])
def list_comments(
    run_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> list[CommentOut]:
    run = _get_run(db, access.project.id, run_id)
    comments = db.scalars(select(Comment).where(Comment.run_id == run.id).order_by(Comment.id)).all()
    return [_comment_out(c) for c in comments]
