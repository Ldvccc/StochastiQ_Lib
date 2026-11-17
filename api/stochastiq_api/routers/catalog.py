from fastapi import APIRouter, HTTPException, Query, status

from stochastiq import ansatz_structure, build_ansatz, circuit_stats

from ..catalog import ANSATZ_NAMES, ansatz_catalog, topology_catalog

router = APIRouter(tags=["catalogue"])


@router.get("/ansatz")
def list_ansatz() -> list[dict]:
    """Les 7 ansatz : nom technique, nom d'affichage, description, nombre de paramètres."""
    return ansatz_catalog()


@router.get("/ansatz/{name}/structure")
def structure(
    name: str,
    n_qubits: int = Query(ge=2, le=8),
    layers: int = Query(ge=1, le=8),
) -> dict:
    """Circuit en colonnes de portes (``stochastiq.ansatz_structure``), pour le dessin,
    et ses statistiques (``stochastiq.circuit_stats``) sous la clé ``stats``."""
    if name not in ANSATZ_NAMES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ansatz inconnu.")
    return {
        **ansatz_structure(name, n_qubits, layers),
        "stats": circuit_stats(build_ansatz(name, n_qubits, layers)),
    }


@router.get("/topologies")
def list_topologies() -> list[dict]:
    return topology_catalog()
