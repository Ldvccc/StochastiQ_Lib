from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import Membership, Project, User
from .roles import ROLE_LABELS, has_role
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)

NOT_FOUND = "Projet introuvable."


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Utilisateur authentifié par le jeton ``Authorization: Bearer`` (401 sinon)."""
    user_id = None
    if credentials is not None:
        user_id = decode_token(credentials.credentials, request.app.state.settings.secret_key)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentification requise ou jeton invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@dataclass
class ProjectAccess:
    """Projet demandé, utilisateur courant et son adhésion."""

    project: Project
    user: User
    membership: Membership


def require_role(min_role: str) -> Callable[..., ProjectAccess]:
    """Dépendance : l'utilisateur doit être membre du projet avec au moins ``min_role``.

    Un non-membre reçoit 404, pour ne pas révéler l'existence du projet ;
    un membre au rôle insuffisant reçoit 403.
    """

    def dependency(
        project_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> ProjectAccess:
        membership = db.get(Membership, (project_id, user.id))
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
        if not has_role(membership.role, min_role):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Droit insuffisant : rôle « {ROLE_LABELS[min_role]} » au minimum requis.",
            )
        return ProjectAccess(project=membership.project, user=user, membership=membership)

    return dependency
