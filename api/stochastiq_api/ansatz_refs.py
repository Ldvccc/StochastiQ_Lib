"""Résolution des ansatz personnalisés dans les paramètres d'un run.

Un run accepte ``ansatz = "nom du catalogue"`` ou ``{"custom_id": n}``. Avant
l'enregistrement, chaque identifiant est remplacé par l'ansatz complet
(``{"custom": {id, name, format, content, n_qubits}}``) : le run reste
reproductible tel quel, même si l'ansatz est ensuite modifié ou supprimé.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import CustomAnsatz
from .routers.custom_ansatz import build_circuit


def _resolve_one(db: Session, project_id: int, ref):
    if isinstance(ref, str):
        return ref
    ansatz = db.get(CustomAnsatz, ref["custom_id"])
    if ansatz is None or ansatz.project_id != project_id:
        raise HTTPException(422, f"Ansatz personnalisé n° {ref['custom_id']} introuvable dans ce projet.")
    return {
        "custom": {
            "id": ansatz.id,
            "name": ansatz.name,
            "format": ansatz.format,
            "content": ansatz.content,
            "n_qubits": ansatz.n_qubits,
        }
    }


def _check_buildable(custom: dict, n_qubits: int, layers: int) -> None:
    try:
        build_circuit(custom["format"], custom["content"], n_qubits, layers)
    except ValueError as error:
        raise HTTPException(422, f"« {custom['name']} » : {error}") from error


def resolve_params(db: Session, project_id: int, kind: str, params: dict) -> dict:
    """Remplace les identifiants d'ansatz personnalisés et vérifie qu'ils sont constructibles."""
    params = dict(params)
    single = not isinstance(params.get("ansatz"), list)
    refs = [params["ansatz"]] if single else params["ansatz"]
    resolved = [_resolve_one(db, project_id, ref) for ref in refs]
    for ref in resolved:
        if isinstance(ref, str):
            continue
        custom = ref["custom"]
        fixed = custom["n_qubits"]
        if kind == "scaling":
            if fixed is not None:
                raise HTTPException(
                    422,
                    f"« {custom['name']} » fixe {fixed} qubits : une étude de scaling demande un ansatz "
                    "paramétrable en nombre de qubits (spec sans motif « custom »).",
                )
            for n_qubits in range(params["qubit_min"], params["qubit_max"] + 1):
                layers = params["layers"] if params["layers_mode"] == "fixed" else n_qubits
                _check_buildable(custom, n_qubits, layers)
        else:
            if fixed is not None and params["n_qubits"] != fixed:
                raise HTTPException(
                    422, f"« {custom['name']} » fixe {fixed} qubits, mais le run en demande {params['n_qubits']}."
                )
            _check_buildable(custom, params["n_qubits"], params["layers"])
    params["ansatz"] = resolved[0] if single else resolved
    return params
