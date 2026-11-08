"""IA de prédiction : TVD finale après entraînement exact, et dégradation sous bruit.

Cibles :

- ``final_tvd`` : TVD entre la cible et la distribution apprise, entraînement
  exact (lignes ``training`` sans tirages) ;
- ``degradation`` : TVD sous bruit moins TVD exacte, mêmes paramètres appris
  (lignes ``training_noise``).

Entrées : caractéristiques du circuit, du problème et (pour la dégradation)
du bruit ; jamais l'identifiant du projet ni le nom de l'ansatz.

Références à battre :

- moyenne par ansatz (empreinte), moyenne globale pour un ansatz inconnu ;
- pour la dégradation seulement, fidélité par comptage des portes
  F = (1 - p1)^n1 · (1 - p2)^n2 · (1 - lecture)^n, convertie en dégradation
  par a · (1 - F), le coefficient a étant ajusté par moindres carrés sur les
  données d'entraînement.

Modèle : ``HistGradientBoostingRegressor`` (``random_state`` fixé) pour la
valeur centrale, entraîné sur tout le jeu d'entraînement.

Intervalle 10-90 %, calibrage conforme des quantiles (CQR, Romano et al. 2019) :
deux modèles quantiles (10 % et 90 %) sont entraînés sur 75 % du jeu
d'entraînement ; les 25 % restants (tirage aléatoire, graine 0), jamais le
test, donnent les scores E = max(q10 - y, y - q90) et la marge q̂, ⌈(n + 1)·0,8⌉-ième
plus petit score ; l'intervalle est [q10 - q̂, q90 + q̂]. Méthode fixée par
l'auteur, sans autre ajustement.

Validations : un ansatz laissé de côté, une famille de distributions laissée
de côté, entraînement sur 2 à 5 qubits et test sur 6, et un découpage
aléatoire en 5 plis. Critères, séparés (dérogation au critère initial,
validée par l'auteur) :

- valeur centrale : le modèle est retenu si son MAE est au moins 20 % sous la
  meilleure référence, sur la validation qui correspond au cas ; sinon la
  référence sert de prédiction ;
- intervalle : affiché seulement si sa couverture mesurée (après CQR) sur la
  validation qui correspond au cas est entre 70 % et 90 %.

Validation qui correspond au cas : celles dont la situation s'applique
(ansatz inconnu, famille inconnue, nombre de qubits hors de la plage
apprise) ; s'il y en a plusieurs, la plus défavorable ; s'il n'y en a
aucune, le découpage aléatoire.
"""

import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_STATE = 0
QUANTILES = (0.1, 0.9)
ALPHA = QUANTILES[0] + (1 - QUANTILES[1])
CALIBRATION_FRACTION = 0.25
MAE_GAIN = 0.2
COVERAGE_RANGE = (0.7, 0.9)
RANDOM_FOLDS = 5
MODEL_FILE = "predictor.joblib"

VALIDATIONS = {
    "ansatz_laisse_de_cote": "Ansatz laissé de côté",
    "famille_laissee_de_cote": "Famille laissée de côté",
    "qubits_2_5_vers_6": "Entraînement sur 2 à 5 qubits, test sur 6",
    "aleatoire": "Découpage aléatoire en 5 plis",
}

CIRCUIT_FEATURES = [
    "layers",
    "circuit_n_qubits",
    "circuit_n_parameters",
    "circuit_depth",
    "circuit_n_two_qubit_gates",
    "circuit_n_one_qubit_gates",
    "circuit_line_n1",
    "circuit_line_n2",
    "circuit_line_depth",
]
PROBLEM_FEATURES = ["problem_entropy", "problem_support_fraction", "problem_max_probability", "problem_mean_mutual_information"]
NOISE_FEATURES = ["noise_p1", "noise_p2", "noise_readout", "q_n1", "q_n2"]

TARGETS = {
    "final_tvd": {"label": "TVD finale après entraînement exact", "features": CIRCUIT_FEATURES + PROBLEM_FEATURES, "column": "q_tvd"},
    "degradation": {
        "label": "Dégradation sous bruit (TVD bruitée moins TVD exacte)",
        "features": CIRCUIT_FEATURES + PROBLEM_FEATURES + NOISE_FEATURES,
        "column": "q_degradation",
    },
}


def target_rows(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    """Lignes utiles à une cible : entraînements exacts, ou évaluations sous bruit."""
    if frame.empty:
        return frame
    if target == "final_tvd":
        rows = frame[frame["type"] == "training"]
        if "q_shots" in rows:
            rows = rows[rows["q_shots"].isna()]
    else:
        rows = frame[frame["type"] == "training_noise"]
    columns = TARGETS[target]["features"] + [TARGETS[target]["column"]]
    return rows.dropna(subset=[c for c in columns if c in rows]).reset_index(drop=True)


def gate_fidelity(rows: pd.DataFrame) -> np.ndarray:
    return (
        (1 - rows["noise_p1"]) ** rows["q_n1"]
        * (1 - rows["noise_p2"]) ** rows["q_n2"]
        * (1 - rows["noise_readout"]) ** rows["circuit_n_qubits"]
    ).to_numpy()


class References:
    """Références ajustées sur un jeu d'entraînement."""

    def __init__(self, train: pd.DataFrame, target: str):
        y = train[TARGETS[target]["column"]]
        self.global_mean = float(y.mean())
        self.by_ansatz = {key: float(value) for key, value in y.groupby(train["ansatz_fingerprint"]).mean().items()}
        self.fidelity_coef = None
        if target == "degradation":
            x = 1 - gate_fidelity(train)
            denominator = float(x @ x)
            self.fidelity_coef = float(x @ y.to_numpy() / denominator) if denominator > 0 else 0.0

    def predictions(self, rows: pd.DataFrame) -> dict[str, np.ndarray]:
        result = {"ansatz_mean": rows["ansatz_fingerprint"].map(self.by_ansatz).fillna(self.global_mean).to_numpy(dtype=float)}
        if self.fidelity_coef is not None:
            result["gate_fidelity"] = self.fidelity_coef * (1 - gate_fidelity(rows))
        return result

    def to_dict(self) -> dict:
        return {"global_mean": self.global_mean, "by_ansatz": self.by_ansatz, "fidelity_coef": self.fidelity_coef}


def conformal_margin(scores: np.ndarray, alpha: float = ALPHA) -> float:
    """Marge CQR : ⌈(n + 1)(1 - alpha)⌉-ième plus petit score (infinie si n est trop petit)."""
    n = len(scores)
    rank = math.ceil((n + 1) * (1 - alpha))
    if n == 0 or rank > n:
        return math.inf
    return float(np.sort(scores)[rank - 1])


def fit_models(train: pd.DataFrame, target: str) -> dict:
    """Modèle central (tout le jeu), modèles quantiles (75 %) et marge CQR (25 % de calibrage)."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    features, column = TARGETS[target]["features"], TARGETS[target]["column"]
    x = train[features].to_numpy(dtype=float)
    y = train[column].to_numpy(dtype=float)
    models = {"point": HistGradientBoostingRegressor(random_state=RANDOM_STATE).fit(x, y)}
    order = np.random.default_rng(RANDOM_STATE).permutation(len(train))
    n_cal = int(round(CALIBRATION_FRACTION * len(train)))
    cal, proper = order[:n_cal], order[n_cal:]
    for q in QUANTILES:
        models[q] = HistGradientBoostingRegressor(loss="quantile", quantile=q, random_state=RANDOM_STATE).fit(x[proper], y[proper])
    low, high = _raw_interval(models, x[cal])
    models["margin"] = conformal_margin(np.maximum(low - y[cal], y[cal] - high))
    return models


def _raw_interval(models: dict, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    low, high = models[QUANTILES[0]].predict(x), models[QUANTILES[1]].predict(x)
    return np.minimum(low, high), np.maximum(low, high)


def predict_models(models: dict, rows: pd.DataFrame, target: str) -> dict[str, np.ndarray]:
    """Valeur centrale, intervalle brut des quantiles et intervalle calibré (CQR)."""
    x = rows[TARGETS[target]["features"]].to_numpy(dtype=float)
    raw_low, raw_high = _raw_interval(models, x)
    return {
        "point": models["point"].predict(x),
        "raw_low": raw_low,
        "raw_high": raw_high,
        "low": raw_low - models["margin"],
        "high": raw_high + models["margin"],
    }


def splits(rows: pd.DataFrame) -> dict[str, list[np.ndarray]]:
    """Masques des jeux de test de chaque validation."""
    from sklearn.model_selection import KFold

    random_folds = []
    for _, test in KFold(RANDOM_FOLDS, shuffle=True, random_state=RANDOM_STATE).split(rows):
        mask = np.zeros(len(rows), dtype=bool)
        mask[test] = True
        random_folds.append(mask)
    return {
        "ansatz_laisse_de_cote": [(rows["ansatz_fingerprint"] == key).to_numpy() for key in sorted(rows["ansatz_fingerprint"].unique())],
        "famille_laissee_de_cote": [(rows["problem_family"] == key).to_numpy() for key in sorted(rows["problem_family"].dropna().unique())],
        "qubits_2_5_vers_6": [(rows["n_qubits"] == 6).to_numpy()],
        "aleatoire": random_folds,
    }


def validate(rows: pd.DataFrame, target: str) -> dict:
    """Les quatre validations d'une cible ; prédictions regroupées sur tous les plis d'une validation."""
    y_all = rows[TARGETS[target]["column"]].to_numpy(dtype=float)
    report = {}
    for name, folds in splits(rows).items():
        collected: dict[str, list] = {}
        refs: dict[str, list] = {}
        margins = []
        for test in folds:
            train = rows[~test]
            if train.empty or not test.any():
                continue
            models = fit_models(train, target)
            margins.append(models["margin"])
            for key, values in predict_models(models, rows[test], target).items():
                collected.setdefault(key, []).append(values)
            collected.setdefault("y", []).append(y_all[test])
            for ref_name, values in References(train, target).predictions(rows[test]).items():
                refs.setdefault(ref_name, []).append(values)
        c = {key: np.concatenate(values) for key, values in collected.items()}
        y = c["y"]
        ref_pred = {ref: np.concatenate(values) for ref, values in refs.items()}
        ref_mae = {ref: float(np.mean(np.abs(values - y))) for ref, values in ref_pred.items()}
        best_ref = min(ref_mae, key=ref_mae.get)
        mae = float(np.mean(np.abs(c["point"] - y)))
        gain = 1 - mae / ref_mae[best_ref] if ref_mae[best_ref] > 0 else 0.0
        coverage_raw = float(np.mean((y >= c["raw_low"]) & (y <= c["raw_high"])))
        coverage = float(np.mean((y >= c["low"]) & (y <= c["high"])))
        report[name] = {
            "label": VALIDATIONS[name],
            "n_test": int(len(y)),
            "n_folds": len(folds),
            "mae": mae,
            "reference_mae": ref_mae,
            "best_reference": best_ref,
            "gain": float(gain),
            "point_model": bool(gain >= MAE_GAIN),
            "coverage_raw": coverage_raw,
            "width_raw": float(np.mean(c["raw_high"] - c["raw_low"])),
            "coverage": coverage,
            "width": float(np.mean(c["high"] - c["low"])),
            "mean_margin": float(np.mean(margins)),
            "interval_reliable": bool(COVERAGE_RANGE[0] <= coverage <= COVERAGE_RANGE[1]),
            "reference_residual_quantiles": [float(np.quantile(ref_pred[best_ref] - y, q)) for q in QUANTILES],
        }
    return report


def train_predictor(frame: pd.DataFrame, library_version: str) -> dict:
    """Valide puis entraîne chaque cible sur toutes les lignes ; retourne le paquet à sauvegarder."""
    bundle = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "library_version": library_version,
        "criteria": {
            "mae_gain": MAE_GAIN,
            "coverage_range": list(COVERAGE_RANGE),
            "quantiles": list(QUANTILES),
            "calibration_fraction": CALIBRATION_FRACTION,
        },
        "targets": {},
    }
    for target, spec in TARGETS.items():
        rows = target_rows(frame, target)
        if len(rows) < 50:
            raise ValueError(f"{spec['label']} : {len(rows)} lignes seulement, 50 au moins sont nécessaires.")
        report = validate(rows, target)
        bundle["targets"][target] = {
            "label": spec["label"],
            "features": spec["features"],
            "n_rows": int(len(rows)),
            "validations": report,
            "known": {
                "ansatz": sorted(rows["ansatz_fingerprint"].unique()),
                "families": sorted(rows["problem_family"].dropna().unique()),
                "qubits": [int(rows["n_qubits"].min()), int(rows["n_qubits"].max())],
            },
            "references": References(rows, target).to_dict(),
            "models": fit_models(rows, target),
        }
    return bundle


def save_bundle(bundle: dict, models_dir: str | Path) -> Path:
    import joblib

    path = Path(models_dir)
    path.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path / MODEL_FILE)
    return path / MODEL_FILE


def load_bundle(models_dir: str | Path) -> dict | None:
    """Paquet sauvegardé, ou None si aucun modèle n'a été entraîné."""
    path = Path(models_dir) / MODEL_FILE
    if not path.exists():
        return None
    import joblib

    return joblib.load(path)


def report_of(bundle: dict) -> dict:
    """Paquet sans les modèles (sérialisable en JSON)."""
    return {
        **{k: v for k, v in bundle.items() if k != "targets"},
        "targets": {name: {k: v for k, v in t.items() if k != "models"} for name, t in bundle["targets"].items()},
    }


def matching_validation(spec: dict, features: dict) -> tuple[str, list[str]]:
    """Validation qui correspond au cas, et situations du cas (ansatz, famille, qubits inconnus)."""
    known = spec["known"]
    situations = []
    if features.get("ansatz_fingerprint") not in known["ansatz"]:
        situations.append("ansatz_laisse_de_cote")
    if features.get("problem_family") not in known["families"]:
        situations.append("famille_laissee_de_cote")
    if not known["qubits"][0] <= features["n_qubits"] <= known["qubits"][1]:
        situations.append("qubits_2_5_vers_6")
    if not situations:
        return "aleatoire", situations
    validations = spec["validations"]
    # Plusieurs situations : la validation la plus défavorable (couverture la plus éloignée de 80 %, puis gain le plus bas).
    worst = max(situations, key=lambda v: (abs(validations[v]["coverage"] - 0.8), -validations[v]["gain"]))
    return worst, situations


def format_percent(value: float) -> str:
    return f"{100 * value:.1f} %".replace(".", ",")


def predict(bundle: dict, target: str, features: dict) -> dict:
    """Prédiction d'une cible pour une ligne de caractéristiques (mêmes noms de colonnes que l'export)."""
    spec = bundle["targets"][target]
    row = pd.DataFrame([features])
    refs = spec["references"]
    reference = {"ansatz_mean": refs["by_ansatz"].get(features.get("ansatz_fingerprint"), refs["global_mean"])}
    if refs["fidelity_coef"] is not None:
        reference["gate_fidelity"] = float(refs["fidelity_coef"] * (1 - gate_fidelity(row)[0]))
    validation_name, situations = matching_validation(spec, features)
    validation = spec["validations"][validation_name]
    output = {key: float(values[0]) for key, values in predict_models(spec["models"], row, target).items()}
    if validation["point_model"]:
        value, source = output["point"], "model"
    else:
        value, source = float(reference[validation["best_reference"]]), "reference"
    reliable = validation["interval_reliable"] and source == "model"
    return {
        "value": value,
        "source": source,
        "reference_name": validation["best_reference"],
        "references": reference,
        "low": output["low"] if reliable else None,
        "high": output["high"] if reliable else None,
        "interval_reliable": reliable,
        "interval_message": None
        if reliable
        else "Intervalle non affiché : la référence sert de prédiction pour ce cas."
        if source == "reference"
        else f"Intervalle non fiable pour ce cas : couverture mesurée {format_percent(validation['coverage'])}.",
        "validation": validation_name,
        "validation_label": validation["label"],
        "situations": situations,
        "coverage": validation["coverage"],
        "gain": validation["gain"],
    }
