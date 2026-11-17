"""Prédiction pour un ansatz, un problème et un profil de bruit (route /predict, recommandation)."""

from stochastiq import circuit_features, resolve_profile, transpiled_gate_counts

from ..runner import make_circuit
from .predictor import predict
from .results import fingerprint

NO_MODEL = "Aucun modèle entraîné : lancez scripts/train_predictor.py."


def feature_row(
    ref, n_qubits: int, layers: int, problem_features: dict, problem_family: str | None, profile=None, topology: str = "line"
) -> dict:
    """Caractéristiques au format de l'export de la base de résultats (préfixes circuit_, problem_, noise_, q_)."""
    circuit = make_circuit(ref, n_qubits, layers)
    row = {"ansatz_fingerprint": fingerprint(ref), "problem_family": problem_family, "n_qubits": n_qubits, "layers": layers}
    row.update({f"circuit_{k}": v for k, v in circuit_features(circuit).items()})
    row.update({f"problem_{k}": v for k, v in problem_features.items()})
    if profile is not None:
        row.update({f"noise_{k}": v for k, v in resolve_profile(profile).items()})
        counts = transpiled_gate_counts(circuit, topology, seed=0)
        row.update({"q_n1": counts["n1"], "q_n2": counts["n2"]})
    return row


def prediction(
    bundle: dict, ref, n_qubits: int, layers: int, problem_features: dict, problem_family: str | None, profile=None, topology: str = "line"
) -> dict:
    """TVD finale prédite et, avec un profil de bruit, dégradation et TVD sous bruit prédites.

    L'intervalle de la TVD sous bruit (somme des deux intervalles) n'est donné que si les deux sont fiables.
    """
    row = feature_row(ref, n_qubits, layers, problem_features, problem_family, profile, topology)
    final = predict(bundle, "final_tvd", row)
    result = {"final_tvd": final, "degradation": None, "noisy_tvd": None}
    if profile is not None:
        degradation = predict(bundle, "degradation", row)
        result["degradation"] = degradation
        reliable = final["interval_reliable"] and degradation["interval_reliable"]
        result["noisy_tvd"] = {
            "value": final["value"] + degradation["value"],
            "low": final["low"] + degradation["low"] if reliable else None,
            "high": final["high"] + degradation["high"] if reliable else None,
            "interval_reliable": reliable,
        }
    return result


def model_info(bundle: dict) -> dict:
    return {
        "created_at": bundle["created_at"],
        "library_version": bundle["library_version"],
        "targets": {
            name: {
                "label": t["label"],
                "n_rows": t["n_rows"],
                "validations": {
                    v: {
                        key: d[key]
                        for key in ("label", "mae", "gain", "best_reference", "reference_mae", "point_model", "coverage_raw", "coverage", "interval_reliable")
                    }
                    for v, d in t["validations"].items()
                },
            }
            for name, t in bundle["targets"].items()
        },
    }
