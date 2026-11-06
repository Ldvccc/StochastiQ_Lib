from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

MIGRATIONS = Path(__file__).parent / "migrations"


class Base(DeclarativeBase):
    """Base des modèles SQLAlchemy."""


def utcnow() -> datetime:
    """Date et heure UTC sans fuseau (SQLite ne conserve pas le fuseau)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def make_engine(database_url: str) -> Engine:
    """Crée le moteur ; pour SQLite, active les clés étrangères et le partage entre fils."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(database_url: str) -> None:
    """Applique les migrations Alembic jusqu'à la dernière version."""
    command.upgrade(alembic_config(database_url), "head")


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête."""
    with request.app.state.sessionmaker() as session:
        yield session
