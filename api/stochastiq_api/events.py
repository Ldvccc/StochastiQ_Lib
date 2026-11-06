from sqlalchemy.orm import Session

from .models import ActivityEvent

# Types d'événements du fil d'activité.
EVENT_TYPES = (
    "run_launched",
    "run_done",
    "run_failed",
    "comment_added",
    "circuit_pinned",
    "member_invited",
    "member_joined",
    "role_changed",
    "machine_added",
)


def record(db: Session, project_id: int, user_id: int | None, type: str, payload: dict) -> None:
    """Ajoute un événement au fil d'activité (validé avec la transaction en cours)."""
    assert type in EVENT_TYPES, type
    db.add(ActivityEvent(project_id=project_id, user_id=user_id, type=type, payload=payload))
