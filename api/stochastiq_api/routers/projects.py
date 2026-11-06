import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ProjectAccess, get_current_user, require_role
from ..models import Membership, Project, User
from ..roles import MIN_ROLE
from ..schemas import MemberOut, MemberPatch, ProjectIn, ProjectOut, ProjectPatch

router = APIRouter(tags=["projets"])


def _slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "projet"


def _unique_slug(db: Session, name: str) -> str:
    base = slug = _slugify(name)
    suffix = 2
    while db.scalar(select(Project.id).where(Project.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _fields(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "created_by": project.created_by,
        "created_at": project.created_at,
    }


def _member_out(membership: Membership) -> MemberOut:
    return MemberOut(
        user_id=membership.user_id,
        email=membership.user.email,
        name=membership.user.name,
        role=membership.role,
        title=membership.title,
        created_at=membership.created_at,
    )


def _owner_count(db: Session, project_id: int) -> int:
    return db.scalar(
        select(func.count()).where(Membership.project_id == project_id, Membership.role == "owner")
    )


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list:
    """Projets dont l'utilisateur est membre, avec son rôle."""
    rows = db.execute(
        select(Project, Membership.role)
        .join(Membership, Membership.project_id == Project.id)
        .where(Membership.user_id == user.id)
        .order_by(Project.created_at.desc(), Project.id.desc())
    ).all()
    return [ProjectOut(**_fields(project), role=role) for project, role in rows]


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProjectOut:
    """Crée un projet ; son créateur en devient propriétaire."""
    project = Project(
        name=data.name, slug=_unique_slug(db, data.name), description=data.description, created_by=user.id
    )
    db.add(project)
    db.flush()
    db.add(Membership(project_id=project.id, user_id=user.id, role="owner"))
    db.commit()
    return ProjectOut(**_fields(project), role="owner")


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(access: ProjectAccess = Depends(require_role(MIN_ROLE["read"]))) -> ProjectOut:
    return ProjectOut(**_fields(access.project), role=access.membership.role)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    data: ProjectPatch,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["edit_project"])),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = db.merge(access.project)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    db.commit()
    return ProjectOut(**_fields(project), role=access.membership.role)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    access: ProjectAccess = Depends(require_role(MIN_ROLE["delete_project"])),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(db.merge(access.project))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def list_members(
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])), db: Session = Depends(get_db)
) -> list[MemberOut]:
    memberships = db.scalars(
        select(Membership)
        .where(Membership.project_id == access.project.id)
        .order_by(Membership.created_at, Membership.user_id)
    ).all()
    return [_member_out(m) for m in memberships]


def _get_member(db: Session, project_id: int, user_id: int) -> Membership:
    membership = db.get(Membership, (project_id, user_id))
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membre introuvable.")
    return membership


LAST_OWNER = "Le dernier propriétaire du projet ne peut être ni rétrogradé ni retiré."


@router.patch("/projects/{project_id}/members/{user_id}", response_model=MemberOut)
def update_member(
    user_id: int,
    data: MemberPatch,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["manage_members"])),
    db: Session = Depends(get_db),
) -> MemberOut:
    """Change le rôle et/ou le titre d'un membre (propriétaire uniquement)."""
    membership = _get_member(db, access.project.id, user_id)
    if data.role is not None and data.role != membership.role:
        if membership.role == "owner" and _owner_count(db, access.project.id) == 1:
            raise HTTPException(status.HTTP_409_CONFLICT, LAST_OWNER)
        membership.role = data.role
    if data.title is not None:
        membership.title = data.title
    db.commit()
    return _member_out(membership)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["manage_members"])),
    db: Session = Depends(get_db),
) -> Response:
    membership = _get_member(db, access.project.id, user_id)
    if membership.role == "owner" and _owner_count(db, access.project.id) == 1:
        raise HTTPException(status.HTTP_409_CONFLICT, LAST_OWNER)
    db.delete(membership)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
