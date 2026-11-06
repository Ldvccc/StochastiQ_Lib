"""Fil d'activité, circuits épinglés et machines d'un projet."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ProjectAccess, require_role
from ..events import record
from ..models import ActivityEvent, Machine, PinnedCircuit
from ..roles import MIN_ROLE
from ..run_schemas import ActivityOut, ActivityPage, MachineIn, MachineOut, PinIn, PinOut, UserRef

router = APIRouter(tags=["collaboration"])


@router.get("/projects/{project_id}/activity", response_model=ActivityPage)
def activity(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])),
    db: Session = Depends(get_db),
) -> ActivityPage:
    """Événements du projet, du plus récent au plus ancien."""
    query = select(ActivityEvent).where(ActivityEvent.project_id == access.project.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    events = db.scalars(query.order_by(ActivityEvent.id.desc()).limit(limit).offset(offset)).all()
    return ActivityPage(
        items=[
            ActivityOut(
                id=event.id,
                type=event.type,
                user=UserRef(id=event.user.id, name=event.user.name) if event.user else None,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in events
        ],
        total=total,
    )


def _pin_out(pin: PinnedCircuit) -> PinOut:
    return PinOut(
        id=pin.id,
        ansatz=pin.ansatz,
        n_qubits=pin.n_qubits,
        layers=pin.layers,
        pinned_by=pin.pinned_by,
        created_at=pin.created_at,
    )


@router.get("/projects/{project_id}/pins", response_model=list[PinOut])
def list_pins(
    access: ProjectAccess = Depends(require_role(MIN_ROLE["read"])), db: Session = Depends(get_db)
) -> list[PinOut]:
    pins = db.scalars(
        select(PinnedCircuit).where(PinnedCircuit.project_id == access.project.id).order_by(PinnedCircuit.id)
    ).all()
    return [_pin_out(pin) for pin in pins]


@router.post("/projects/{project_id}/pins", response_model=PinOut, status_code=status.HTTP_201_CREATED)
def pin_circuit(
    data: PinIn,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["pin"])),
    db: Session = Depends(get_db),
) -> PinOut:
    exists = db.scalar(
        select(PinnedCircuit.id).where(
            PinnedCircuit.project_id == access.project.id,
            PinnedCircuit.ansatz == data.ansatz,
            PinnedCircuit.n_qubits == data.n_qubits,
            PinnedCircuit.layers == data.layers,
        )
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce circuit est déjà épinglé.")
    pin = PinnedCircuit(project_id=access.project.id, pinned_by=access.user.id, **data.model_dump())
    db.add(pin)
    db.flush()
    record(db, access.project.id, access.user.id, "circuit_pinned", data.model_dump())
    db.commit()
    return _pin_out(pin)


@router.delete("/projects/{project_id}/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpin_circuit(
    pin_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["pin"])),
    db: Session = Depends(get_db),
) -> Response:
    pin = db.get(PinnedCircuit, pin_id)
    if pin is None or pin.project_id != access.project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Circuit épinglé introuvable.")
    db.delete(pin)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _machine_out(machine: Machine) -> MachineOut:
    return MachineOut(
        id=machine.id,
        provider=machine.provider,
        label=machine.label,
        created_by=machine.created_by,
        created_at=machine.created_at,
    )


@router.get("/projects/{project_id}/machines", response_model=list[MachineOut])
def list_machines(
    access: ProjectAccess = Depends(require_role(MIN_ROLE["machines"])), db: Session = Depends(get_db)
) -> list[MachineOut]:
    """Entrées « fournisseur + libellé » du projet (aucune clé n'est stockée)."""
    machines = db.scalars(
        select(Machine).where(Machine.project_id == access.project.id).order_by(Machine.id)
    ).all()
    return [_machine_out(m) for m in machines]


@router.post("/projects/{project_id}/machines", response_model=MachineOut, status_code=status.HTTP_201_CREATED)
def add_machine(
    data: MachineIn,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["machines"])),
    db: Session = Depends(get_db),
) -> MachineOut:
    machine = Machine(project_id=access.project.id, created_by=access.user.id, **data.model_dump())
    db.add(machine)
    db.flush()
    record(db, access.project.id, access.user.id, "machine_added", data.model_dump())
    db.commit()
    return _machine_out(machine)


@router.delete("/projects/{project_id}/machines/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_machine(
    machine_id: int,
    access: ProjectAccess = Depends(require_role(MIN_ROLE["machines"])),
    db: Session = Depends(get_db),
) -> Response:
    machine = db.get(Machine, machine_id)
    if machine is None or machine.project_id != access.project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine introuvable.")
    db.delete(machine)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
