"""Calculs exécutés dans un processus séparé (aucun accès à la base ici).

Chaque fonction n'appelle que la bibliothèque ``stochastiq`` et retourne un
résultat sérialisable en JSON standard (les ``NaN`` deviennent ``None``).
"""

import json
import math

import numpy as np

from stochastiq import (
    build_ansatz,
    classical_baselines,
    distribution_metrics,
    noisy_probabilities,
    noisy_tvd,
    problem_features,
    train_qcbm,
    build_from_spec,
    load_qasm,
    validate_ansatz,
    circuit_stats,
    compare,
    entangling_capability,
    expressibility,
    fidelity_histogram,
    fit_decay,
    gradient_scaling,
    gradient_variance_details,
    hardware_cost,
    pareto_front,
)


def to_json(value):
    """Convertit récursivement les types numpy en types JSON ; ``NaN`` et infinis en ``None``."""
    if isinstance(value, dict):
        return {str(key): to_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return to_json(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(value) else float(value)
    return value


def make_circuit(ref, n_qubits: int, layers: int):
    """Circuit d'un ansatz du catalogue (nom) ou personnalisé (``{"custom": {...}}``, résolu par l'API)."""
    if isinstance(ref, str):
        return build_ansatz(ref, n_qubits, layers)
    custom = ref["custom"]
    if custom["format"] == "spec":
        return validate_ansatz(build_from_spec(json.loads(custom["content"]), n_qubits, layers))
    return validate_ansatz(load_qasm(custom["content"]))


def ansatz_key(ref) -> str:
    """Nom affiché d'un ansatz dans les résultats (nom du catalogue ou nom donné par le client)."""
    return ref if isinstance(ref, str) else ref["custom"]["name"]


# Tirages de la carte « Dégradation sous bruit » du diagnostic (topologie en ligne).
DIAGNOSTIC_NOISE_SAMPLES = 20


def _diagnostic(p: dict) -> dict:
    ansatz = make_circuit(p["ansatz"], p["n_qubits"], p["layers"])
    gradient = gradient_variance_details(
        ansatz, n_samples=p["n_samples"], observable=p["observable"], seed=p["seed"]
    )
    return {
        "expressibility": expressibility(ansatz, n_samples=p["n_samples"], seed=p["seed"]),
        "entangling_capability": entangling_capability(ansatz, n_samples=p["n_samples"], seed=p["seed"]),
        "gradient": {
            "mean_variance": gradient["mean_variance"],
            "active_mean_variance": gradient["active_mean_variance"],
            "inactive_fraction": gradient["inactive_fraction"],
            "n_inactive_parameters": gradient["n_inactive_parameters"],
            "n_parameters": len(gradient["variance_per_parameter"]),
        },
        "stats": circuit_stats(ansatz),
        "histogram": fidelity_histogram(ansatz, n_samples=p["n_samples"], seed=p["seed"]),
        "noise": (
            noisy_tvd(ansatz, p["noise_profile"], "line", n_samples=DIAGNOSTIC_NOISE_SAMPLES, seed=p["seed"])
            if p.get("noise_profile") is not None
            else None
        ),
    }


def _compare(p: dict) -> dict:
    circuits = {}
    for ref in p["ansatz"]:
        key = ansatz_key(ref)
        while key in circuits:  # un nom personnalisé peut répéter un nom du catalogue
            key += " (personnalisé)"
        circuits[key] = make_circuit(ref, p["n_qubits"], p["layers"])
    df = compare(circuits, n_samples=p["n_samples"], seed=p["seed"], n_seeds=p["n_seeds"])
    front = pareto_front(list(zip(df["expressibility"], df["gradient_variance_active"])))
    rows = [
        {"ansatz": name, **row, "pareto": on_front}
        for (name, row), on_front in zip(df.to_dict(orient="index").items(), front)
    ]
    return {"rows": rows}


def _scaling(p: dict) -> dict:
    observables = ["Z0", "Zall"] if p["compare_observables"] else [p["observable"]]
    series = []
    for observable in observables:
        for ref in p["ansatz"]:
            df = gradient_scaling(
                ref if isinstance(ref, str) else (lambda n, layers, ref=ref: make_circuit(ref, n, layers)),
                range(p["qubit_min"], p["qubit_max"] + 1),
                layers=p["layers"],
                layers_mode=p["layers_mode"],
                n_samples=p["n_samples"],
                observable=observable,
                seed=p["seed"],
            )
            series.append(
                {
                    "ansatz": ansatz_key(ref),
                    "observable": observable,
                    "rows": df.to_dict(orient="records"),
                    "fit_active": fit_decay(df["n_qubits"], df["active_mean_variance"]),
                    "fit_all": fit_decay(df["n_qubits"], df["mean_variance"]),
                }
            )
    return {"series": series}


def _hardware(p: dict) -> dict:
    ansatz = make_circuit(p["ansatz"], p["n_qubits"], p["layers"])
    return hardware_cost(ansatz, topology=p["topology"], seed=p["seed"])


def evaluate_under_noise(ansatz, learned, target, evaluation: dict, seed: int) -> dict:
    """Métriques de la distribution bruitée obtenue avec les paramètres appris ``learned``."""
    noisy = noisy_probabilities(ansatz, learned, evaluation["profile"], evaluation["topology"], seed)
    return {**evaluation, "probabilities": noisy, "metrics": distribution_metrics(target, noisy)}


def _training(p: dict) -> dict:
    ansatz = make_circuit(p["ansatz"], p["n_qubits"], p["layers"])
    result = train_qcbm(
        ansatz,
        p["target"],
        loss=p["loss"],
        optimizer=p["optimizer"],
        max_iter=p["max_iter"],
        learning_rate=p["learning_rate"],
        shots=p["shots"],
        seed=p["seed"],
    )
    noise = None
    if p.get("evaluate_noise") is not None:
        noise = evaluate_under_noise(ansatz, result["params"], p["target"], p["evaluate_noise"], p["seed"])
    return {
        **result,
        "baselines": classical_baselines(p["target"]),
        "problem_features": problem_features(p["target"]),
        "noise": noise,
    }


def _noise(p: dict) -> dict:
    ansatz = make_circuit(p["ansatz"], p["n_qubits"], p["layers"])
    return noisy_tvd(ansatz, p["profile"], p["topology"], n_samples=p["n_samples"], seed=p["seed"])


KINDS = {
    "diagnostic": _diagnostic,
    "compare": _compare,
    "scaling": _scaling,
    "hardware": _hardware,
    "training": _training,
    "noise": _noise,
}


def execute(kind: str, params: dict, models_dir: str | None = None) -> dict:
    """Exécute un run et retourne son résultat sérialisable (``models_dir`` : modèle de prédiction)."""
    if kind == "recommendation":
        from .ml.recommendation import run_recommendation

        return to_json(run_recommendation(params, models_dir))
    return to_json(KINDS[kind](params))
