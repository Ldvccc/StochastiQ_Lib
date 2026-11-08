"""Base de résultats : une ligne par grandeur mesurée, alimentée par les runs réussis et par la grille.

Une ligne garde les caractéristiques du circuit (``circuit_features``), celles
du problème (``problem_features``, jamais le vecteur de probabilités), le
profil de bruit et les grandeurs mesurées. Types de lignes :

- ``diagnostic`` : expressibilité, intrication, variance du gradient ;
- ``noise`` : TVD moyenne idéal / bruité sur des paramètres aléatoires ;
- ``training`` : métriques finales d'un entraînement exact, références classiques ;
- ``training_noise`` : mêmes paramètres appris, métriques sous bruit et dégradation
  (TVD bruitée moins TVD exacte).

L'IA ne s'entraîne que sur les lignes de la grille de référence et sur celles
des projets qui ont activé ``share_results`` (voir ``eligible_query``).
"""

import hashlib
import logging
from pathlib import Path

import stochastiq
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from stochastiq import circuit_features, resolve_profile, transpiled_gate_counts

from ..models import Project, Result, Run
from ..runner import ansatz_key, make_circuit

logger = logging.getLogger(__name__)

RECORDED_KINDS = ("diagnostic", "noise", "training")


def fingerprint(ref) -> str:
    """Empreinte stable d'un ansatz : nom du catalogue, ou hachage du contenu d'un ansatz personnalisé."""
    if isinstance(ref, str):
        return f"cat:{ref}"
    custom = ref["custom"]
    digest = hashlib.sha256(f"{custom['format']}\n{custom['content']}".encode()).hexdigest()
    return f"custom:{digest[:16]}"


def _base(ref, n_qubits: int, layers: int, features: dict) -> dict:
    return {
        "ansatz": ansatz_key(ref),
        "ansatz_fingerprint": fingerprint(ref),
        "n_qubits": n_qubits,
        "layers": layers,
        "circuit_features": features,
        "problem_family": None,
        "problem_features": None,
        "noise_profile": None,
        "noise_topology": None,
    }


def _noise_columns(circuit, profile, topology: str, seed: int) -> tuple[dict, dict]:
    """Taux du profil et portes du circuit transpilé sur la topologie du bruit."""
    counts = transpiled_gate_counts(circuit, topology, seed)
    return {"noise_profile": resolve_profile(profile), "noise_topology": topology}, {"n1": counts["n1"], "n2": counts["n2"]}


def noise_row(base: dict, circuit, profile, noise: dict, seed: int) -> dict:
    columns, counts = _noise_columns(circuit, profile, noise["topology"], seed)
    quantities = {"mean_tvd": noise["mean_tvd"], "std_tvd": noise["std_tvd"], "n_samples": len(noise["tvds"]), "seed": seed}
    return {**base, **columns, "type": "noise", "quantities": {**quantities, **counts}}


def training_rows(base: dict, circuit, params: dict, result: dict, evaluations: list[dict]) -> list[dict]:
    """Ligne ``training`` puis une ligne ``training_noise`` par évaluation sous bruit."""
    problem = {**base, "problem_family": params.get("problem_family"), "problem_features": result["problem_features"]}
    baselines = {name: b["metrics"]["tvd"] for name, b in result["baselines"].items()}
    metrics = result["metrics"]
    rows = [
        {
            **problem,
            "type": "training",
            "quantities": {
                **metrics,
                "loss": result["loss"],
                "optimizer": result["optimizer"],
                "n_iterations": result["n_iterations"],
                "max_iter": params["max_iter"],
                "learning_rate": params["learning_rate"],
                "shots": params["shots"],
                "seed": params["seed"],
                "baseline_independent_tvd": baselines["independent"],
                "baseline_chow_liu_tvd": baselines["chow_liu"],
                "best_baseline_tvd": min(baselines.values()),
            },
        }
    ]
    for evaluation in evaluations:
        columns, counts = _noise_columns(circuit, evaluation["profile"], evaluation["topology"], params["seed"])
        noisy = evaluation["metrics"]
        quantities = {
            "tvd_exact": metrics["tvd"],
            "tvd_noisy": noisy["tvd"],
            "kl_noisy": noisy["kl"],
            "hellinger_noisy": noisy["hellinger"],
            "degradation": noisy["tvd"] - metrics["tvd"],
            "seed": params["seed"],
        }
        rows.append({**problem, **columns, "type": "training_noise", "quantities": {**quantities, **counts}})
    return rows


def run_rows(kind: str, params: dict, result: dict) -> list[dict]:
    """Lignes de la base de résultats pour un run réussi (liste vide pour les autres types de runs)."""
    if kind not in RECORDED_KINDS:
        return []
    circuit = make_circuit(params["ansatz"], params["n_qubits"], params["layers"])
    base = _base(params["ansatz"], params["n_qubits"], params["layers"], circuit_features(circuit))
    if kind == "noise":
        return [noise_row(base, circuit, params["profile"], result, params["seed"])]
    if kind == "training":
        evaluations = [result["noise"]] if result.get("noise") else []
        return training_rows(base, circuit, params, result, evaluations)
    gradient = result["gradient"]
    rows = [
        {
            **base,
            "type": "diagnostic",
            "quantities": {
                "expressibility": result["expressibility"],
                "entangling_capability": result["entangling_capability"],
                "gradient_mean_variance": gradient["mean_variance"],
                "gradient_active_mean_variance": gradient["active_mean_variance"],
                "inactive_fraction": gradient["inactive_fraction"],
                "n_samples": params["n_samples"],
                "observable": params["observable"],
                "seed": params["seed"],
            },
        }
    ]
    if result.get("noise"):
        rows.append(noise_row(base, circuit, params["noise_profile"], result["noise"], params["seed"]))
    return rows


def record_run(db: Session, run: Run) -> int:
    """Ajoute à la session les lignes d'un run réussi ; retourne leur nombre (sans valider la transaction)."""
    rows = run_rows(run.kind, run.params, run.result)
    for row in rows:
        db.add(
            Result(
                source="run",
                run_id=run.id,
                project_id=run.project_id,
                library_version=stochastiq.__version__,
                **row,
            )
        )
    return len(rows)


def eligible_query():
    """Lignes utilisables par l'IA : grille de référence et projets qui partagent leurs résultats."""
    shared = select(Project.id).where(Project.share_results.is_(True))
    return select(Result).where(or_(Result.source == "grid", Result.project_id.in_(shared))).order_by(Result.id)


def flatten(result: Result) -> dict:
    """Ligne plate pour l'export : colonnes simples, puis ``circuit_*``, ``problem_*``, ``noise_*`` et ``q_*``."""
    row = {
        "id": result.id,
        "source": result.source,
        "type": result.type,
        "run_id": result.run_id,
        "project_id": result.project_id,
        "ansatz": result.ansatz,
        "ansatz_fingerprint": result.ansatz_fingerprint,
        "n_qubits": result.n_qubits,
        "layers": result.layers,
        "problem_family": result.problem_family,
        "noise_topology": result.noise_topology,
        "library_version": result.library_version,
        "created_at": result.created_at.isoformat(),
    }
    for prefix, values in (
        ("circuit", result.circuit_features),
        ("problem", result.problem_features),
        ("noise", result.noise_profile),
        ("q", result.quantities),
    ):
        for key, value in (values or {}).items():
            row[f"{prefix}_{key}"] = value
    return row


def results_frame(db: Session, eligible_only: bool = True):
    """Tableau pandas de la base de résultats (lignes éligibles à l'IA par défaut)."""
    import pandas as pd

    query = eligible_query() if eligible_only else select(Result).order_by(Result.id)
    return pd.DataFrame([flatten(result) for result in db.scalars(query)])


def export_results(db: Session, path: str | Path, eligible_only: bool = True) -> int:
    """Exporte la base en CSV (``.csv``) ou Parquet (``.parquet``, demande pyarrow) ; retourne le nombre de lignes."""
    path = Path(path)
    if path.suffix not in (".csv", ".parquet"):
        raise ValueError("Format d'export : .csv ou .parquet.")
    frame = results_frame(db, eligible_only)
    if path.suffix == ".csv":
        frame.to_csv(path, index=False)
    else:
        try:
            frame.to_parquet(path, index=False)
        except ImportError as error:
            raise ValueError("L'export Parquet demande pyarrow (pip install pyarrow) ; utilisez .csv sinon.") from error
    return len(frame)
