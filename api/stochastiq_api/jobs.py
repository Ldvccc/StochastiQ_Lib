"""Exécution des runs hors du processus de l'API.

Au plus ``MAX_WORKERS`` calculs tournent en même temps. Chaque run s'exécute
dans son propre ``ProcessPoolExecutor`` à un seul worker : un calcul de la
bibliothèque ne peut pas être interrompu en cours de route, et ce découpage
permet de tuer le seul processus d'un run qui dépasse la durée maximale,
sans toucher aux autres calculs.
"""

import logging
import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from .db import utcnow
from .events import record
from .models import Run
from .runner import execute

logger = logging.getLogger(__name__)

MAX_WORKERS = 2

ORPHAN_MESSAGE = "Interrompu : l'API a redémarré avant la fin du calcul."


def mark_orphans_failed(sessions: sessionmaker[Session]) -> int:
    """Au démarrage, passe en « failed » les runs restés « pending » ou « running »."""
    with sessions() as db:
        result = db.execute(
            update(Run)
            .where(Run.status.in_(("pending", "running")))
            .values(status="failed", error=ORPHAN_MESSAGE, finished_at=utcnow())
        )
        db.commit()
        return result.rowcount


def format_duration(seconds: float) -> str:
    """Durée en français : « 0,5 seconde », « 1 minute », « 10 minutes ».

    Minutes à partir de 60 secondes ; pluriel à partir de 2 (règle française).
    """
    value, unit = (seconds / 60, "minute") if seconds >= 60 else (seconds, "seconde")
    return f"{value:g}".replace(".", ",") + f" {unit}" + ("s" if value >= 2 else "")


def _kill(executor: ProcessPoolExecutor) -> None:
    """Termine les processus d'un exécuteur (API publique en Python 3.14, attribut privé avant)."""
    terminate = getattr(executor, "terminate_workers", None)
    if terminate is not None:
        terminate()
    else:
        for process in list(getattr(executor, "_processes", {}).values()):
            process.kill()
    executor.shutdown(wait=False, cancel_futures=True)


class RunManager:
    """Ordonnanceur des runs : file d'attente, exécution, durée maximale, statut en base."""

    def __init__(self, sessions: sessionmaker[Session], timeout_seconds: float):
        self._sessions = sessions
        self._timeout = timeout_seconds
        self._dispatcher = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="run")
        self._active: set[ProcessPoolExecutor] = set()
        self._lock = threading.Lock()

    def submit(self, run_id: int) -> None:
        self._dispatcher.submit(self._run, run_id)

    def _finish(self, run_id: int, status: str, result: dict | None, error: str | None) -> None:
        with self._sessions() as db:
            run = db.get(Run, run_id)
            if run is None:  # projet supprimé pendant le calcul
                return
            run.status, run.result, run.error, run.finished_at = status, result, error, utcnow()
            event = "run_done" if status == "done" else "run_failed"
            payload = {"run_id": run.id, "kind": run.kind}
            if error:
                payload["error"] = error
            record(db, run.project_id, run.created_by, event, payload)
            db.commit()

    def _run(self, run_id: int) -> None:
        with self._sessions() as db:
            run = db.get(Run, run_id)
            if run is None or run.status != "pending":
                return
            run.status, run.started_at = "running", utcnow()
            kind, params = run.kind, dict(run.params)
            db.commit()

        executor = ProcessPoolExecutor(max_workers=1)
        with self._lock:
            self._active.add(executor)
        try:
            result = executor.submit(execute, kind, params).result(timeout=self._timeout)
        except FutureTimeout:
            _kill(executor)
            message = f"Durée maximale dépassée ({format_duration(self._timeout)})."
            self._finish(run_id, "failed", None, message)
        except Exception as error:  # échec du calcul : message court, sans trace
            logger.warning("Run %s en échec : %s", run_id, type(error).__name__)
            self._finish(run_id, "failed", None, f"{type(error).__name__} : {error}")
        else:
            self._finish(run_id, "done", result, None)
        finally:
            executor.shutdown(wait=False)
            with self._lock:
                self._active.discard(executor)

    def shutdown(self) -> None:
        """Arrête les calculs en cours (les runs interrompus seront repris comme orphelins)."""
        self._dispatcher.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            for executor in list(self._active):
                _kill(executor)
