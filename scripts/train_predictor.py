"""Entraînement et validation de l'IA de prédiction (voir docs/PREDICTION.md).

Lit les lignes éligibles de la base de résultats (grille de référence et
projets qui partagent leurs résultats), lance les quatre validations pour
chaque cible, puis entraîne les modèles sur toutes les lignes et les écrit
dans MODELS_DIR (``predictor.joblib``, plus ``predictor_report.json``, sans
les modèles).

Utilisation, depuis la racine du dépôt (PowerShell) :

    .venv\\Scripts\\python scripts\\train_predictor.py
    .venv\\Scripts\\python scripts\\train_predictor.py --database-url sqlite:///./data/results.db
    .venv\\Scripts\\python scripts\\train_predictor.py --csv data\\results_grid.csv --models-dir api\\models

Modèle réduit (lignes à 1 couche seulement), pour les tests de bout en bout :

    .venv\\Scripts\\python scripts\\train_predictor.py --csv data\\results_grid.csv --layers 1 --models-dir <dossier>
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import stochastiq

from stochastiq_api.config import Settings
from stochastiq_api.db import make_engine, make_sessionmaker, upgrade_database
from stochastiq_api.ml.predictor import report_of, save_bundle, train_predictor
from stochastiq_api.ml.results import results_frame


def percent(value: float) -> str:
    return f"{100 * value:.1f} %".replace(".", ",")


def main() -> int:
    parser = argparse.ArgumentParser(description="Entraîne et valide l'IA de prédiction.")
    parser.add_argument("--database-url", default=None, help="Base de résultats (par défaut : DATABASE_URL).")
    parser.add_argument("--csv", default=None, help="Export CSV de la base, à la place de la base.")
    parser.add_argument("--models-dir", default=None, help="Dossier de sortie (par défaut : MODELS_DIR).")
    parser.add_argument(
        "--layers", type=int, nargs="+", default=None, help="Ne garde que ces nombres de couches (modèle réduit, pour les tests)."
    )
    args = parser.parse_args()

    settings = Settings()
    if args.csv:
        frame = pd.read_csv(args.csv)
    else:
        database_url = args.database_url or settings.database_url
        upgrade_database(database_url)
        with make_sessionmaker(make_engine(database_url))() as db:
            frame = results_frame(db)
    if args.layers:
        frame = frame[frame["layers"].isin(args.layers)]
    print(f"{len(frame)} lignes éligibles.")

    bundle = train_predictor(frame, stochastiq.__version__)
    report = report_of(bundle)
    for name, target in report["targets"].items():
        print(f"\n{target['label']} ({target['n_rows']} lignes)")
        for v in target["validations"].values():
            refs = ", ".join(f"{ref} {mae:.4f}" for ref, mae in v["reference_mae"].items())
            point = "modèle retenu" if v["point_model"] else "référence retenue"
            interval = "intervalle affiché" if v["interval_reliable"] else "intervalle non affiché"
            print(
                f"  {v['label']} : MAE {v['mae']:.4f} (références : {refs}), gain {percent(v['gain'])} -> {point} ; "
                f"couverture 10-90 % {percent(v['coverage_raw'])} avant CQR, {percent(v['coverage'])} après -> {interval}"
            )

    models_dir = Path(args.models_dir or settings.models_dir)
    path = save_bundle(bundle, models_dir)
    (models_dir / "predictor_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nModèle écrit dans {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
