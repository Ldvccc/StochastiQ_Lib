import math
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("streamlit")
pytest.importorskip("matplotlib")

from streamlit.testing.v1 import AppTest  # noqa: E402

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
sys.path.insert(0, str(DASHBOARD))

import ui  # noqa: E402

APP = str(DASHBOARD / "app.py")


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def test_app_demarre_sans_exception(app):
    assert not app.exception


def test_chaque_onglet_s_affiche(app):
    assert [tab.label for tab in app.tabs] == ["Diagnostic", "Comparateur", "Ansatz", "Matériel"]
    for tab, title in zip(app.tabs, ["Diagnostic", "Comparateur", "Ansatz", "Matériel"]):
        assert tab.header[0].value == title
    assert not app.error


def test_diagnostiquer_affiche_les_3_cartes():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.slider(key="diag_qubits").set_value(2)
    at.slider(key="diag_layers").set_value(1)
    at.number_input(key="diag_samples").set_value(100)
    at.button(key="diag_run").click().run()
    assert not at.exception
    assert not at.error
    cards = at.tabs[0].metric
    assert [card.label for card in cards] == [
        "Expressibilité",
        "Intrication",
        "Variance du gradient",
    ]


def _compare_df(with_std: bool) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "n_qubits": [4, 4, 4],
            "n_parameters": [24, 24, 12],
            "depth": [18, 18, 10],
            "n_two_qubit_gates": [12, 12, 9],
            "expressibility": [0.0115, 0.0115, 0.1955],
            "entangling_capability": [0.836, 0.836, 0.679],
            "gradient_variance": [0.030, 0.030, 0.229],
        },
        index=["strongly_entangling", "ryrz_circular", "ry_linear"],
    )
    if with_std:
        for metric in ui.METRICS:
            df[f"{metric}_std"] = 0.001
    return df


def test_format_value():
    assert ui.format_value(0.14160234) == "0.1416"
    assert ui.format_value(0.00012) == "1.200e-04"
    assert ui.format_value(0) == "0.0000"
    assert ui.format_value(math.nan) == "n/a"


def test_format_overhead():
    assert ui.format_overhead(3.0) == "×3.00"
    assert ui.format_overhead(math.nan) == "n/a"


def test_compare_table_sans_std():
    table = ui.compare_table(_compare_df(with_std=False))
    assert list(table.index) == ["strongly_entangling", "ryrz_circular", "ry_linear"]
    assert table.loc["ry_linear", "Expressibilité"] == "0.1955"
    assert "±" not in table.loc["ry_linear", "Intrication"]


def test_compare_table_avec_std():
    table = ui.compare_table(_compare_df(with_std=True))
    assert table.loc["ry_linear", "Expressibilité"] == "0.1955 ± 0.0010"
    assert list(table.columns) == [ui.METRIC_LABELS[k] for k in ui.METRIC_LABELS]


def test_phrase_de_lecture_cite_les_ex_aequo():
    sentence = ui.reading_sentence(_compare_df(with_std=False))
    assert "« strongly_entangling » et « ryrz_circular »" in sentence
    assert "0.0115" in sentence
    assert "0.8360" in sentence
    assert "ry_linear" not in sentence


def test_phrase_de_lecture_un_seul_gagnant():
    df = _compare_df(with_std=True).drop(index="ryrz_circular")
    sentence = ui.reading_sentence(df)
    assert sentence.startswith("Le circuit le plus expressif est « strongly_entangling »")
    assert "moyennes sur les graines" in sentence


def test_phrase_de_lecture_tableau_vide():
    assert ui.reading_sentence(_compare_df(with_std=False).iloc[0:0]) == ""


def test_stats_et_portes():
    stats = {
        "n_qubits": 4,
        "n_parameters": 12,
        "depth": 10,
        "n_two_qubit_gates": 9,
        "gate_counts": {"cx": 9, "ry": 12},
    }
    assert ui.stats_table(stats)["Valeur"].tolist() == [4, 12, 10, 9]
    assert ui.gate_counts_table(stats)["Nombre"].to_dict() == {"ry": 12, "cx": 9}


def _cost(after_gates: int, after_depth: int) -> dict:
    return {
        "topology": "line",
        "before": {"n_two_qubit_gates": 12, "depth": 15},
        "basis_only": {"n_two_qubit_gates": 12, "depth": 31},
        "after": {"n_two_qubit_gates": after_gates, "depth": after_depth},
        "routing_overhead_two_qubit": after_gates / 12,
    }


def test_hardware_table():
    table = ui.hardware_table(_cost(36, 58))
    assert list(table.columns) == ["Circuit d'origine", "Après traduction", "Après routage"]
    assert table.index.name == "Topologie : Ligne"
    assert table.loc["Portes à 2 qubits"].tolist() == [12, 12, 36]
    assert table.loc["Profondeur"].tolist() == [15, 31, 58]


def test_libelles_des_topologies():
    assert [ui.topology_label(t) for t in ["line", "ring", "full", "heavy_hex"]] == [
        "Ligne",
        "Anneau",
        "Complète",
        "Hexagone lourd",
    ]


def test_phrase_materiel_avec_routage():
    sentence = ui.hardware_sentence(_cost(36, 58))
    assert "topologie Ligne" in sentence
    assert "de 12 à 36" in sentence
    assert "de 31 à 58" in sentence


def test_phrase_materiel_sans_routage():
    sentence = ui.hardware_sentence(_cost(12, 31))
    assert "n'ajoute aucune porte à 2 qubits" in sentence
    assert "31" in sentence
