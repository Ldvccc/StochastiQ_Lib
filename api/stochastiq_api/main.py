"""Point d'entrée de l'API : ``uvicorn stochastiq_api.main:app``."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings
from .db import make_engine, make_sessionmaker, upgrade_database
from .jobs import RunManager, mark_orphans_failed
from .routers import auth, catalog, collaboration, invitations, meta, projects, runs
from .security import MaskInvitationTokens


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construit l'application ; lève ``RuntimeError`` si la configuration n'est pas sûre."""
    settings = settings or Settings()
    settings.check()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        upgrade_database(settings.database_url)
        mark_orphans_failed(app.state.sessionmaker)
        app.state.runs = RunManager(app.state.sessionmaker, settings.run_timeout_seconds)
        yield
        app.state.runs.shutdown()
        app.state.engine.dispose()

    app = FastAPI(
        title="API StochastiQ",
        version=__version__,
        description="Prototype universitaire : comptes, projets, rôles et diagnostics d'ansatz.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.sessionmaker = make_sessionmaker(app.state.engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    for router in (
        meta.router,
        auth.router,
        projects.router,
        invitations.router,
        catalog.router,
        runs.router,
        collaboration.router,
    ):
        app.include_router(router)

    # Les jetons d'invitation apparaissent dans des chemins d'URL : on les masque.
    logging.getLogger("uvicorn.access").addFilter(MaskInvitationTokens())
    return app


app = create_app()
