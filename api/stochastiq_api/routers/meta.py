from fastapi import APIRouter

from .. import __version__
from ..roles import PERMISSIONS, ROLE_LABELS, ROLES

router = APIRouter(tags=["méta"])


@router.get("/health")
def health() -> dict:
    """Vérification de disponibilité (utilisée par le healthcheck Docker)."""
    return {"status": "ok", "version": __version__}


@router.get("/roles")
def roles() -> dict:
    """Rôles et matrice de droits (rôle minimal par action), pour l'interface."""
    return {
        "roles": [{"name": role, "label": ROLE_LABELS[role]} for role in ROLES],
        "permissions": PERMISSIONS,
    }
