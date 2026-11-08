from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # Si vrai, les résultats du projet servent à entraîner l'IA de prédiction (choix du propriétaire).
    share_results: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Membership(Base):
    __tablename__ = "memberships"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))
    # Étiquette libre (CEO, CTO...), sans effet sur les droits.
    title: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship()


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (UniqueConstraint("token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    token: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    project: Mapped[Project] = relationship()


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User | None] = relationship()


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User | None] = relationship()


class PinnedCircuit(Base):
    __tablename__ = "pinned_circuits"
    __table_args__ = (UniqueConstraint("project_id", "ansatz", "n_qubits", "layers"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    ansatz: Mapped[str] = mapped_column(String(40))
    n_qubits: Mapped[int] = mapped_column(Integer)
    layers: Mapped[int] = mapped_column(Integer)
    pinned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Machine(Base):
    """Entrée « fournisseur + libellé ». Aucune clé ni secret n'est stocké (hors périmètre)."""

    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Problem(Base):
    """Distribution cible d'un client. Le contenu d'un CSV importé n'est pas conservé, seulement le vecteur."""

    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    n_qubits: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(20))  # "reference" ou "csv"
    probabilities: Mapped[list] = mapped_column(JSON)
    source_params: Mapped[dict] = mapped_column(JSON, default=dict)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CustomAnsatz(Base):
    """Ansatz du client : spec JSON normalisée ou texte OpenQASM, validés à l'enregistrement."""

    __tablename__ = "custom_ansatz"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    format: Mapped[str] = mapped_column(String(10))  # "spec" ou "qasm"
    content: Mapped[str] = mapped_column(Text)
    n_qubits: Mapped[int | None] = mapped_column(Integer, nullable=True)  # fixé (QASM, spec « custom »), sinon None
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Result(Base):
    """Ligne de la base de résultats : caractéristiques et grandeurs mesurées, jamais de probabilités brutes.

    ``source`` vaut « grid » (grille de référence, scripts/build_results.py)
    ou « run » (run réussi d'un projet). ``config_key`` identifie une
    configuration de la grille (doublons ignorés), None pour un run.
    """

    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(10), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    config_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    ansatz: Mapped[str] = mapped_column(String(120))
    ansatz_fingerprint: Mapped[str] = mapped_column(String(80), index=True)
    n_qubits: Mapped[int] = mapped_column(Integer)
    layers: Mapped[int] = mapped_column(Integer)
    circuit_features: Mapped[dict] = mapped_column(JSON)
    problem_family: Mapped[str | None] = mapped_column(String(40), nullable=True)
    problem_features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    noise_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    noise_topology: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quantities: Mapped[dict] = mapped_column(JSON)
    library_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
