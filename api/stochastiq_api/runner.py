"""Calculs exécutés dans un processus séparé (aucun accès à la base ici).

Chaque fonction n'appelle que la bibliothèque ``stochastiq`` et retourne un
résultat sérialisable en JSON standard (les ``NaN`` deviennent ``None``).
"""

import math

import numpy as np

from stochastiq import (
    build_ansatz,
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


def _diagnostic(p: dict) -> dict:
    ansatz = build_ansatz(p["ansatz"], p["n_qubits"], p["layers"])
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
    }


def _compare(p: dict) -> dict:
    circuits = {name: build_ansatz(name, p["n_qubits"], p["layers"]) for name in p["ansatz"]}
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
        for name in p["ansatz"]:
            df = gradient_scaling(
                name,
                range(p["qubit_min"], p["qubit_max"] + 1),
                layers=p["layers"],
                layers_mode=p["layers_mode"],
                n_samples=p["n_samples"],
                observable=observable,
                seed=p["seed"],
            )
            series.append(
                {
                    "ansatz": name,
                    "observable": observable,
                    "rows": df.to_dict(orient="records"),
                    "fit_active": fit_decay(df["n_qubits"], df["active_mean_variance"]),
                    "fit_all": fit_decay(df["n_qubits"], df["mean_variance"]),
                }
            )
    return {"series": series}


def _hardware(p: dict) -> dict:
    ansatz = build_ansatz(p["ansatz"], p["n_qubits"], p["layers"])
    return hardware_cost(ansatz, topology=p["topology"], seed=p["seed"])


KINDS = {"diagnostic": _diagnostic, "compare": _compare, "scaling": _scaling, "hardware": _hardware}


def execute(kind: str, params: dict) -> dict:
    """Exécute un run et retourne son résultat sérialisable."""
    return to_json(KINDS[kind](params))
