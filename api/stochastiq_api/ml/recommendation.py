"""Règles de décision de la recommandation (classement, indistinguables, verdict quantique / classique).

Chaque ansatz a une valeur (TVD prédite ou mesurée, sous bruit si un profil
est choisi) et une nature de preuve (``evidence``), qui fixe son intervalle
effectif et la règle de verdict (dérogation validée par l'auteur au jalon 8) :

- ``measured`` (entraînement déjà fait dans le projet, une seule
  initialisation) : intervalle réduit au point ; verdict par la règle des 10 % :
  « justified » si TVD < 0,9 × meilleure TVD classique, « not_justified » si
  TVD > 1,1 ×, sinon « equivalent » (le quantique n'apporte rien) ;
- ``interval`` (prédiction avec intervalle 10-90 % fiable) : « justified » si
  la borne haute est sous la meilleure TVD classique, « not_justified » si la
  borne basse est au-dessus, sinon « undetermined » ;
- ``margin`` (prédiction sans intervalle fiable) : marge de 2 × l'erreur
  absolue moyenne de validation du cas comparable ; « probably_justified » si
  valeur + marge < TVD classique, « probably_not_justified » si valeur − marge
  > TVD classique, sinon « undetermined ». Pour une TVD mesurée combinée à une
  dégradation prédite sans intervalle, la marge couvre aussi l'incertitude de
  la mesure (une seule initialisation) : 0,1 × meilleure TVD classique + 2 ×
  erreur moyenne de la dégradation.

Le verdict suit la preuve de l'ansatz classé premier (valeur la plus basse).
Les ansatz dont l'intervalle effectif recoupe le sien lui sont
« indistinguables ». Pour « undetermined », les ansatz à entraîner sont les
mieux classés, sans entraînement, dont l'intervalle effectif contient la TVD
classique, dans la limite du budget (budget // itérations par entraînement,
au moins 1).

Les phrases sont écrites par le web (convention : phrases de lecture côté web).
"""

ITERATIONS_PER_TRAINING = 200
# Écart relatif sous lequel une TVD mesurée est jugée équivalente à la meilleure TVD classique.
RELATIVE_MARGIN = 0.1
# Marge d'une prédiction sans intervalle fiable, en multiples de l'erreur absolue moyenne de validation.
MAE_MARGIN_FACTOR = 2.0


def overlaps(a: dict, b: dict) -> bool:
    return a["low"] <= b["high"] and b["low"] <= a["high"]


def effective_interval(candidate: dict) -> tuple[float, float]:
    """Intervalle effectif selon la nature de la preuve."""
    if candidate["evidence"] == "measured":
        return candidate["value"], candidate["value"]
    if candidate["evidence"] == "interval":
        return candidate["low"], candidate["high"]
    return candidate["value"] - candidate["margin"], candidate["value"] + candidate["margin"]


def verdict_for(best: dict, classical_tvd: float) -> str:
    """Verdict quantique / classique pour l'ansatz classé premier."""
    if best["evidence"] == "measured":
        if best["value"] < (1 - RELATIVE_MARGIN) * classical_tvd:
            return "justified"
        if best["value"] > (1 + RELATIVE_MARGIN) * classical_tvd:
            return "not_justified"
        return "equivalent"
    if best["high"] < classical_tvd:
        return "justified" if best["evidence"] == "interval" else "probably_justified"
    if best["low"] > classical_tvd:
        return "not_justified" if best["evidence"] == "interval" else "probably_not_justified"
    return "undetermined"


def decide(candidates: list[dict], classical_tvd: float, budget: int) -> dict:
    """Classement et verdict.

    ``candidates`` : dicts avec ``key``, ``value``, ``evidence`` (« measured »,
    « interval » ou « margin »), ``low`` et ``high`` (preuve « interval ») et
    ``margin`` (preuve « margin »). Retourne ``ranking`` (clés dans l'ordre),
    ``best``, ``evidence`` (celle du premier), ``indistinguishable`` (clés qui
    recoupent le premier), ``verdict``, ``to_train`` et ``n_trainings``.
    """
    if len(candidates) < 2:
        raise ValueError("Au moins deux ansatz sont nécessaires.")
    items = []
    for c in candidates:
        low, high = effective_interval(c)
        items.append({**c, "low": low, "high": high})
    items.sort(key=lambda c: (c["value"], c["key"]))
    best = items[0]
    indistinguishable = [c["key"] for c in items[1:] if overlaps(best, c)]
    n_trainings = max(1, budget // ITERATIONS_PER_TRAINING)
    verdict = verdict_for(best, classical_tvd)
    to_train: list[str] = []
    if verdict == "undetermined":
        open_items = [c for c in items if c["evidence"] != "measured" and c["low"] <= classical_tvd <= c["high"]]
        to_train = [c["key"] for c in open_items[:n_trainings]]
    return {
        "ranking": [c["key"] for c in items],
        "best": best["key"],
        "evidence": best["evidence"],
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


def _compared(prediction: dict, measured: dict | None, noisy: bool, classical_tvd: float) -> dict:
    """Valeur comparée d'un ansatz : valeur, intervalle, marge, nature de la preuve et source."""
    final, degradation = prediction["final_tvd"], prediction["degradation"]
    if measured is not None and (not noisy or measured["noisy_tvd"] is not None):
        value = measured["noisy_tvd"] if noisy else measured["tvd"]
        return {"value": value, "low": None, "high": None, "margin": None, "evidence": "measured",
                "source": "measured", "interval_message": None}
    if measured is not None:  # TVD exacte mesurée, dégradation sous bruit prédite
        value = measured["tvd"] + degradation["value"]
        source = "measured_degradation_predicted"
        if degradation["interval_reliable"]:
            return {"value": value, "low": measured["tvd"] + degradation["low"], "high": measured["tvd"] + degradation["high"],
                    "margin": None, "evidence": "interval", "source": source, "interval_message": None}
        # Incertitude de la mesure (une seule initialisation) plus celle de la dégradation prédite.
        margin = RELATIVE_MARGIN * classical_tvd + MAE_MARGIN_FACTOR * degradation["mae"]
        return {"value": value, "low": None, "high": None, "margin": margin,
                "evidence": "margin", "source": source, "interval_message": degradation["interval_message"]}
    if not noisy:
        if final["interval_reliable"]:
            return {"value": final["value"], "low": final["low"], "high": final["high"], "margin": None,
                    "evidence": "interval", "source": final["source"], "interval_message": None}
        return {"value": final["value"], "low": None, "high": None, "margin": MAE_MARGIN_FACTOR * final["mae"],
                "evidence": "margin", "source": final["source"], "interval_message": final["interval_message"]}
    combined = prediction["noisy_tvd"]
    source = "model" if final["source"] == degradation["source"] == "model" else "reference"
    if combined["interval_reliable"]:
        return {"value": combined["value"], "low": combined["low"], "high": combined["high"], "margin": None,
                "evidence": "interval", "source": source, "interval_message": None}
    messages = [m for m in (final["interval_message"], degradation["interval_message"]) if m]
    return {
        "value": combined["value"],
        "low": None,
        "high": None,
        # Somme des erreurs moyennes des deux prédictions additionnées.
        "margin": MAE_MARGIN_FACTOR * (final["mae"] + degradation["mae"]),
        "evidence": "margin",
        "source": source,
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
    baselines = classical_baselines(p["target"])
    tvds = {name: b["metrics"]["tvd"] for name, b in baselines.items()}
    best = min(tvds, key=tvds.get)
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
                **_compared(predicted, measured, noisy, tvds[best]),
            }
        )
    candidates = [
        {key: i[key] for key in ("key", "value", "low", "high", "margin", "evidence")}
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
