"""Règles de décision de la recommandation (classement, indistinguables, verdict quantique / classique).

Chaque ansatz a une valeur (TVD prédite ou mesurée, sous bruit si un profil
est choisi) et un intervalle [bas, haut] :

- entraînement déjà fait dans le projet : valeur mesurée, intervalle réduit à
  ce point (une seule initialisation) ;
- prédiction avec intervalle fiable : intervalle 10-90 % calibré ;
- prédiction sans intervalle fiable : intervalle infini, l'ansatz recoupe
  tous les autres et ne permet de trancher en rien (lecture prudente).

Règles, appliquées à l'ansatz classé premier (valeur la plus basse) :

- les ansatz dont l'intervalle recoupe le sien lui sont « indistinguables » ;
- « justified » si sa borne haute est sous la meilleure TVD classique ;
- « not_justified » si sa borne basse est au-dessus ;
- sinon « undetermined », avec les ansatz à entraîner pour trancher : les
  mieux classés, sans entraînement, dont l'intervalle contient la TVD
  classique, dans la limite du budget (budget // itérations par entraînement,
  au moins 1).

Les phrases sont écrites par le web (convention : phrases de lecture côté web).
"""

import math

ITERATIONS_PER_TRAINING = 200


def overlaps(a: dict, b: dict) -> bool:
    return a["low"] <= b["high"] and b["low"] <= a["high"]


def decide(candidates: list[dict], classical_tvd: float, budget: int) -> dict:
    """Classement et verdict.

    ``candidates`` : dicts avec ``key``, ``value``, ``low``, ``high`` (None
    accepté : intervalle infini) et ``measured`` (booléen). Retourne
    ``ranking`` (clés dans l'ordre), ``best``, ``indistinguishable`` (clés qui
    recoupent le premier), ``verdict``, ``to_train`` et ``n_trainings``.
    """
    if len(candidates) < 2:
        raise ValueError("Au moins deux ansatz sont nécessaires.")
    items = [
        {
            **c,
            "low": -math.inf if c["low"] is None else c["low"],
            "high": math.inf if c["high"] is None else c["high"],
        }
        for c in candidates
    ]
    items.sort(key=lambda c: (c["value"], c["key"]))
    best = items[0]
    indistinguishable = [c["key"] for c in items[1:] if overlaps(best, c)]
    n_trainings = max(1, budget // ITERATIONS_PER_TRAINING)
    to_train: list[str] = []
    if best["high"] < classical_tvd:
        verdict = "justified"
    elif best["low"] > classical_tvd:
        verdict = "not_justified"
    else:
        verdict = "undetermined"
        open_items = [c for c in items if not c["measured"] and c["low"] <= classical_tvd <= c["high"]]
        to_train = [c["key"] for c in open_items[:n_trainings]]
    return {
        "ranking": [c["key"] for c in items],
        "best": best["key"],
        "indistinguishable": indistinguishable,
        "verdict": verdict,
        "to_train": to_train,
        "n_trainings": n_trainings,
    }


# ---- Côté API (lancement) : entraînements déjà faits dans le projet ----


def _same_ansatz(a, b) -> bool:
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    ca, cb = a["custom"], b["custom"]
    return ca["id"] == cb["id"] and ca["content"] == cb["content"]


def existing_trainings(db, project_id: int, params: dict) -> list:
    """Pour chaque ansatz (même ordre), le dernier entraînement réussi du projet sur ce problème et ces couches.

    Retourne ``{run_id, tvd, noisy_tvd}`` ou None ; ``noisy_tvd`` n'est rempli
    que si l'entraînement a été évalué sous le même profil et la même topologie.
    """
    from sqlalchemy import select
    from stochastiq import resolve_profile

    from ..models import Run

    runs = db.scalars(
        select(Run)
        .where(Run.project_id == project_id, Run.kind == "training", Run.status == "done")
        .order_by(Run.id.desc())
    ).all()
    profile = resolve_profile(params["noise_profile"]) if params.get("noise_profile") is not None else None
    found = []
    for ref in params["ansatz"]:
        match = None
        for run in runs:
            p = run.params
            same = p.get("problem_id") == params["problem_id"] and p.get("layers") == params["layers"]
            if same and _same_ansatz(p["ansatz"], ref):
                noise = (run.result or {}).get("noise")
                noisy = None
                if profile is not None and noise and resolve_profile(noise["profile"]) == profile:
                    if noise["topology"] == params["topology"]:
                        noisy = noise["metrics"]["tvd"]
                match = {"run_id": run.id, "tvd": run.result["metrics"]["tvd"], "noisy_tvd": noisy}
                break
        found.append(match)
    return found


# ---- Côté calcul (processus séparé, sans base) ----


def _compared(prediction: dict, measured: dict | None, noisy: bool) -> dict:
    """Valeur comparée d'un ansatz, avec son intervalle et sa source."""
    if measured is not None and (not noisy or measured["noisy_tvd"] is not None):
        value = measured["noisy_tvd"] if noisy else measured["tvd"]
        return {"value": value, "low": value, "high": value, "source": "measured", "interval_message": None}
    if measured is not None:  # TVD exacte mesurée, dégradation sous bruit prédite
        degradation = prediction["degradation"]
        reliable = degradation["interval_reliable"]
        return {
            "value": measured["tvd"] + degradation["value"],
            "low": measured["tvd"] + degradation["low"] if reliable else None,
            "high": measured["tvd"] + degradation["high"] if reliable else None,
            "source": "measured_degradation_predicted",
            "interval_message": None if reliable else degradation["interval_message"],
        }
    final = prediction["final_tvd"]
    if not noisy:
        return {
            "value": final["value"],
            "low": final["low"],
            "high": final["high"],
            "source": final["source"],
            "interval_message": final["interval_message"],
        }
    combined, degradation = prediction["noisy_tvd"], prediction["degradation"]
    messages = [m for m in (final["interval_message"], degradation["interval_message"]) if m]
    return {
        "value": combined["value"],
        "low": combined["low"],
        "high": combined["high"],
        "source": "model" if final["source"] == degradation["source"] == "model" else "reference",
        "interval_message": " ".join(messages) or None,
    }


def run_recommendation(p: dict, models_dir: str | None) -> dict:
    """Diagnostic léger, prédiction ou mesure, références classiques et décision, pour chaque ansatz."""
    from stochastiq import (
        circuit_stats,
        classical_baselines,
        entangling_capability,
        expressibility,
        gradient_variance_details,
        problem_features,
        resolve_profile,
    )

    from ..runner import ansatz_key, make_circuit
    from .predictor import load_bundle
    from .service import NO_MODEL, prediction

    bundle = load_bundle(models_dir) if models_dir else None
    if bundle is None:
        raise RuntimeError(NO_MODEL)
    features = problem_features(p["target"])
    profile = p.get("noise_profile")
    noisy = profile is not None
    items, keys = [], set()
    for ref, measured in zip(p["ansatz"], p["existing"]):
        key = ansatz_key(ref)
        while key in keys:  # un nom personnalisé peut répéter un nom du catalogue
            key += " (personnalisé)"
        keys.add(key)
        circuit = make_circuit(ref, p["n_qubits"], p["layers"])
        stats = circuit_stats(circuit)
        gradient = gradient_variance_details(circuit, n_samples=p["n_samples"], seed=p["seed"])
        predicted = prediction(
            bundle, ref, p["n_qubits"], p["layers"], features, p.get("problem_family"), profile, p["topology"]
        )
        items.append(
            {
                "key": key,
                "ref": ref,
                "diagnostic": {
                    "expressibility": expressibility(circuit, n_samples=p["n_samples"], seed=p["seed"]),
                    "entangling_capability": entangling_capability(circuit, n_samples=p["n_samples"], seed=p["seed"]),
                    "gradient_mean_variance": gradient["mean_variance"],
                    "n_parameters": stats["n_parameters"],
                    "n_two_qubit_gates": stats["n_two_qubit_gates"],
                },
                "prediction": predicted,
                "measured": measured,
                **_compared(predicted, measured, noisy),
            }
        )
    baselines = classical_baselines(p["target"])
    tvds = {name: b["metrics"]["tvd"] for name, b in baselines.items()}
    best = min(tvds, key=tvds.get)
    candidates = [
        {"key": i["key"], "value": i["value"], "low": i["low"], "high": i["high"], "measured": i["measured"] is not None}
        for i in items
    ]
    return {
        "n_qubits": p["n_qubits"],
        "layers": p["layers"],
        "noise_profile": resolve_profile(profile) if noisy else None,
        "topology": p["topology"],
        "budget": p["budget"],
        "problem_features": features,
        "classical": {
            "best": best,
            "best_tvd": tvds[best],
            "baselines": {name: {"tvd": tvds[name], "n_parameters": b["n_parameters"]} for name, b in baselines.items()},
        },
        "items": items,
        "decision": decide(candidates, tvds[best], p["budget"]),
    }
