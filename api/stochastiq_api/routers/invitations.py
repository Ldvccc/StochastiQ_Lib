"""Invitations par lien. Aucun e-mail n'est envoyé : le propriétaire transmet le lien lui-même."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, utcnow
from ..deps import ProjectAccess, get_current_user, require_role
from ..models import Invitation, Membership, User
from ..roles import MIN_ROLE
from ..schemas import InvitationIn, InvitationOut, InvitationPublic

router = APIRouter(tags=["invitations"])

INVITATION_DAYS = 7


def _refresh_status(invitation: Invitation) -> None:
    """Passe une invitation en attente à « expired » si sa date est dépassée."""
    if invitation.status == "pending" and invitation.expires_at < utcnow():
        invitation.status = "expired"


def _out(invitation: Invitation, request: Request) -> InvitationOut:
    base = request.app.state.settings.cors_origin.rstrip("/")
    return InvitationOut(
        id=invitation.id,
        project_id=invitation.project_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        link=f"{base}/invitations/{invitation.token}",
    )


@router.post(
    "/projects/{project_id}/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    data: InvitationIn,
    request: Request,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["invite"])),
    db: Session = Depends(get_db),
) -> InvitationOut:
    """Crée une invitation valable 7 jours et retourne son lien (aucun e-mail envoyé)."""
    project_id = access.project.id
    member = db.scalar(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.project_id == project_id, User.email == data.email)
    )
    if member is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette personne est déjà membre du projet.")
    pending = db.scalars(
        select(Invitation).where(
            Invitation.project_id == project_id,
            Invitation.email == data.email,
            Invitation.status == "pending",
        )
    ).all()
    for invitation in pending:
        _refresh_status(invitation)
    if any(invitation.status == "pending" for invitation in pending):
        raise HTTPException(status.HTTP_409_CONFLICT, "Une invitation est déjà en attente pour cet e-mail.")
    invitation = Invitation(
        project_id=project_id,
        email=data.email,
        role=data.role,
        token=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(days=INVITATION_DAYS),
        created_by=access.user.id,
    )
    db.add(invitation)
    db.commit()
    return _out(invitation, request)


@router.get("/projects/{project_id}/invitations", response_model=list[InvitationOut])
def list_invitations(
    request: Request,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["invite"])),
    db: Session = Depends(get_db),
) -> list[InvitationOut]:
    """Invitations en attente du projet (propriétaire uniquement)."""
    invitations = db.scalars(
        select(Invitation)
        .where(Invitation.project_id == access.project.id, Invitation.status == "pending")
        .order_by(Invitation.created_at.desc())
    ).all()
    for invitation in invitations:
        _refresh_status(invitation)
    db.commit()
    return [_out(i, request) for i in invitations if i.status == "pending"]


@router.delete(
    "/projects/{project_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_invitation(
    invitation_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["invite"])),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.project_id != access.project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation introuvable.")
    if invitation.status == "pending":
        invitation.status = "revoked"
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _by_token(db: Session, token: str) -> Invitation:
    invitation = db.scalar(select(Invitation).where(Invitation.token == token))
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation introuvable.")
    return invitation


@router.get("/invitations/{token}", response_model=InvitationPublic)
def get_invitation(token: str, db: Session = Depends(get_db)) -> InvitationPublic:
    """Informations publiques d'une invitation, pour la page d'acceptation."""
    invitation = _by_token(db, token)
    _refresh_status(invitation)
    db.commit()
    return InvitationPublic(
        project_name=invitation.project.name,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
    )


@router.post("/invitations/{token}/accept", status_code=status.HTTP_200_OK)
def accept_invitation(
    token: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Accepte une invitation ; l'utilisateur connecté doit avoir l'e-mail invité."""
    invitation = _by_token(db, token)
    _refresh_status(invitation)
    if invitation.status == "expired":
        db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Cette invitation a expiré.")
    if invitation.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette invitation n'est plus valable.")
    if invitation.email != user.email:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Cette invitation est destinée à une autre adresse e-mail."
        )
    if db.get(Membership, (invitation.project_id, user.id)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous êtes déjà membre de ce projet.")
    db.add(Membership(project_id=invitation.project_id, user_id=user.id, role=invitation.role))
    invitation.status = "accepted"
    db.commit()
    return {"project_id": invitation.project_id, "role": invitation.role}
