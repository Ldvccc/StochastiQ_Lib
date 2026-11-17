import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select

from stochastiq_api.db import make_engine, make_sessionmaker, upgrade_database
from stochastiq_api.models import Result

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_results.py"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("build_results", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_grille(build):
    configs = build.grid()
    # 7 ansatz × (5 distributions × 5 tailles + Bars-and-Stripes à 4 et 6 qubits) × 4 couches.
    assert len(configs) == 7 * (5 * 5 + 2) * 4
    assert len(set(configs)) == len(configs)
    assert not any(d == "bars_and_stripes" and n not in (4, 6) for _, d, n, _ in configs)


def test_configuration_enregistree_puis_sautee(build, tmp_path):
    url = f"sqlite:///{tmp_path / 'grille.db'}"
    upgrade_database(url)
    sessions = make_sessionmaker(make_engine(url))
    config = ("rotation_only", "gaussian", 2, 1)
    _, rows, seconds = build.compute(config)
    assert seconds > 0
    assert [row["type"] for row in rows] == ["training"] + ["training_noise"] * 3
    assert [row["noise_profile"] for row in rows[1:]] == [
        {"p1": 1e-4, "p2": 5e-4, "readout": 1e-3},
        {"p1": 1e-3, "p2": 5e-3, "readout": 1e-2},
        {"p1": 1e-2, "p2": 2e-2, "readout": 5e-2},
    ]
    assert rows[0]["problem_family"] == "gaussian"
    assert rows[0]["quantities"]["n_iterations"] == 200
    build.save(sessions, rows)
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Result).where(Result.source == "grid")) == 4
    assert config not in build.missing(sessions, [config, ("rotation_only", "gaussian", 3, 1)])
    assert len(build.missing(sessions, [config, ("rotation_only", "gaussian", 3, 1)])) == 1
