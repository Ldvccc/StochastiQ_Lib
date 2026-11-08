"""Modèle de prédiction dès une installation neuve.

Si ``MODELS_DIR`` ne contient pas de modèle, il est entraîné à partir de
l'export de la grille de référence (``data/results_grid.csv``, versionné dans
le dépôt), avec la même méthode que ``scripts/train_predictor.py``. Appelé à
l'entrée du conteneur de l'API (avant uvicorn) et par ``scripts/seed_demo.py``.

Utilisation : ``python -m stochastiq_api.ml.bootstrap [--grid CHEMIN] [--models-dir DOSSIER]``.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from .predictor import MODEL_FILE, report_of, save_bundle, train_predictor

# Chemin par défaut de l'export, relatif au dossier api/ (dossier de travail de l'API, y compris sous Docker).
DEFAULT_GRID = "../data/results_grid.csv"


def ensure_model(models_dir: str | Path, grid_csv: str | Path) -> str:
    """Entraîne le modèle s'il manque ; retourne « present », « trained » ou « no_data »."""
    import pandas as pd
    import stochastiq

    models_dir = Path(models_dir)
    if (models_dir / MODEL_FILE).exists():
        return "present"
    grid_csv = Path(grid_csv)
    if not grid_csv.exists():
        return "no_data"
    bundle = train_predictor(pd.read_csv(grid_csv), stochastiq.__version__)
    save_bundle(bundle, models_dir)
    (models_dir / "predictor_report.json").write_text(json.dumps(report_of(bundle), indent=2, ensure_ascii=False), encoding="utf-8")
    return "trained"


def main() -> int:
    from ..config import Settings

    parser = argparse.ArgumentParser(description="Entraîne le modèle de prédiction s'il est absent de MODELS_DIR.")
    parser.add_argument("--grid", default=DEFAULT_GRID, help="Export CSV de la grille de référence.")
    parser.add_argument("--models-dir", default=None, help="Dossier du modèle (par défaut : MODELS_DIR).")
    args = parser.parse_args()
    models_dir = args.models_dir or Settings().models_dir
    start = time.perf_counter()
    status = ensure_model(models_dir, args.grid)
    if status == "present":
        print(f"Modèle de prédiction présent dans {models_dir}.")
    elif status == "trained":
        print(f"Modèle de prédiction entraîné dans {models_dir} en {time.perf_counter() - start:.0f} s.")
    else:
        # L'API démarre quand même : /predict et les recommandations répondront 409.
        print(f"Aucun modèle dans {models_dir} et export {args.grid} introuvable : prédiction indisponible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
