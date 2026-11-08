import pandas as pd

from conftest import GRID
from stochastiq_api.ml.bootstrap import ensure_model
from stochastiq_api.ml.predictor import load_bundle


def test_entraine_seulement_si_absent(tmp_path):
    grid = tmp_path / "grille.csv"
    frame = pd.read_csv(GRID)
    frame[frame["layers"] == 1].to_csv(grid, index=False)
    models = tmp_path / "models"
    assert ensure_model(models, grid) == "trained"
    assert load_bundle(models) is not None
    assert (models / "predictor_report.json").exists()
    assert ensure_model(models, grid) == "present"


def test_sans_export(tmp_path):
    assert ensure_model(tmp_path / "models", tmp_path / "absent.csv") == "no_data"
    assert load_bundle(tmp_path / "models") is None
