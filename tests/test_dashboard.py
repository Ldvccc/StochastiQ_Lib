import math
import sys
from pathlib import Path

import numpy as np
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
    titles = ["Diagnostic", "Comparateur", "Ansatz", "Matériel", "Plateau stérile"]
    assert [tab.label for tab in app.tabs] == titles
    for tab, title in zip(app.tabs, titles):
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
    assert any("Paramètres inactifs" in c.value for c in at.tabs[0].caption)


def test_avertissement_peu_d_echantillons():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert [info.value for info in at.tabs[0].info] == [ui.LOW_SAMPLES_WARNING]
    assert [info.value for info in at.tabs[1].info] == [ui.LOW_SAMPLES_WARNING]
    at.number_input(key="diag_samples").set_value(1000).run()
    assert not at.tabs[0].info


def test_comparateur_rappelle_les_parametres():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.multiselect(key="cmp_ansatz").set_value(["hardware_efficient", "all_to_all"])
    at.slider(key="cmp_qubits").set_value(2)
    at.slider(key="cmp_layers").set_value(1)
    at.number_input(key="cmp_samples").set_value(50)
    at.slider(key="cmp_n_seeds").set_value(2)
    at.button(key="cmp_run").click().run()
    assert not at.exception
    captions = [caption.value for caption in at.tabs[1].caption]
    assert ui.compare_params_line(50, 0, 2) in captions
    assert any("front de Pareto" in m.value for m in at.tabs[1].markdown)


def test_etude_plateau_sterile():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.multiselect(key="bp_ansatz").set_value(["hardware_efficient"])
    at.slider(key="bp_qubits").set_value((2, 3))
    at.number_input(key="bp_samples").set_value(20)
    at.button(key="bp_run").click().run()
    assert not at.exception
    assert not at.error
    tab = at.tabs[4]
    assert tab.table[0].value.index.tolist() == ["HardwareEfficient"]
    # 2 points seulement : pas d'ajustement possible.
    assert tab.table[0].value.iloc[0, 0] == "données insuffisantes"
    assert any("« HardwareEfficient » : données insuffisantes" in m.value for m in tab.markdown)
    # Relance identique : résultat servi par le cache, sans erreur de rejeu.
    at.button(key="bp_run").click().run()
    assert not at.exception
    assert at.tabs[4].table[0].value.index.tolist() == ["HardwareEfficient"]


def test_avertissement_plage_longue():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.tabs[4].info
    at.slider(key="bp_qubits").set_value((2, 8)).run()
    assert [info.value for info in at.tabs[4].info] == ["Plage au-delà de 6 qubits : calcul plus long."]


def test_compare_params_line():
    assert ui.compare_params_line(300, 0, 1) == "Calcul effectué avec 300 échantillons, graine 0, 1 graine."
    assert ui.compare_params_line(1000, 7, 3).endswith("graine 7, 3 graines.")


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
            "inactive_fraction": [1 / 3, 10 / 36, 13 / 24],
        },
        index=["strongly_entangling", "data_reuploading", "hardware_efficient"],
    )
    if with_std:
        for metric in ui.METRICS:
            df[f"{metric}_std"] = 0.001
    return df


def test_format_fr():
    assert ui.format_fr(0.14160234, 4) == "0,1416"
    assert ui.format_fr(1, 2) == "1,00"
    assert ui.format_fr(-2.5, 1) == "-2,5"
    assert ui.format_fr(12, 0) == "12"
    assert ui.format_fr(math.nan, 4) == "n/a"
    assert ui.format_fr(None, 4) == "n/a"


def test_format_value():
    assert ui.format_value(0.14160234) == "0,1416"
    assert ui.format_value(0.00012) == "0,0001"
    assert ui.format_value(0.000012) == "0,0000"
    assert "e" not in ui.format_value(1.4e-33)
    assert ui.format_value(0) == "0,0000"
    assert ui.format_value(math.nan) == "n/a"


def test_format_overhead():
    assert ui.format_overhead(1.0) == "×1,00"
    assert ui.format_overhead(3.0) == "×3,00"
    assert ui.format_overhead(math.nan) == "n/a"


def test_axes_en_notation_francaise():
    hist = {
        "edges": np.linspace(0, 1, 5),
        "circuit": np.array([0.4, 0.3, 0.2, 0.1]),
        "haar": np.array([0.5, 0.3, 0.15, 0.05]),
    }
    fig = ui.fidelity_figure(hist)
    ax = fig.axes[0]
    assert ax.xaxis.get_major_formatter()(0.25, 0) == "0,25"
    assert ax.yaxis.get_major_formatter()(0.5, 0) == "0,5"
    fig = ui.expressibility_figure(_compare_df(with_std=True))
    assert fig.axes[0].yaxis.get_major_formatter()(0.05, 0) == "0,05"


def test_compare_table_sans_std():
    table = ui.compare_table(_compare_df(with_std=False))
    assert list(table.index) == ["StronglyEntangling", "DataReuploading", "HardwareEfficient"]
    assert table.loc["HardwareEfficient", "Expressibilité"] == "0,1955"
    assert table.loc["HardwareEfficient", "Paramètres inactifs"] == "54,2 %"
    assert "±" not in table.loc["HardwareEfficient", "Intrication"]


def test_compare_table_avec_std():
    table = ui.compare_table(_compare_df(with_std=True))
    assert table.loc["HardwareEfficient", "Expressibilité"] == "0,1955 ± 0,0010"
    assert list(table.columns) == [ui.METRIC_LABELS[k] for k in ui.METRIC_LABELS]


def _metrics_df(expr, ent, std=None) -> pd.DataFrame:
    df = pd.DataFrame(
        {"expressibility": expr, "entangling_capability": ent},
        index=[f"c{i}" for i in range(len(expr))],
    )
    if std is not None:
        df["expressibility_std"] = std
        df["entangling_capability_std"] = std
    return df


def test_phrase_une_graine_ecart_net():
    df = _metrics_df(expr=[0.01, 0.05, 0.2], ent=[0.5, 0.9, 0.6])
    sentence = ui.reading_sentence(df)
    assert "Le circuit le plus expressif est « c0 »" in sentence
    assert "La plus forte intrication est obtenue par « c1 »" in sentence
    assert "bruit" not in sentence
    assert "graines" not in sentence


def test_phrase_une_graine_ecart_flou():
    df = _metrics_df(expr=[0.100, 0.105, 0.3], ent=[0.80, 0.78, 0.5])
    sentence = ui.reading_sentence(df)
    assert "plus expressif" not in sentence
    assert "plus forte intrication" not in sentence
    assert sentence.count("du même ordre que le bruit d'échantillonnage") == 2
    assert "relancez avec plusieurs graines" in sentence


def test_phrase_plusieurs_graines_gagnant_net():
    df = _metrics_df(expr=[0.01, 0.05], ent=[0.9, 0.6], std=[0.005, 0.005])
    sentence = ui.reading_sentence(df)
    assert "Le circuit le plus expressif est « c0 »" in sentence
    assert "La plus forte intrication est obtenue par « c0 »" in sentence
    assert "Valeurs moyennes sur les graines." in sentence


def test_phrase_plusieurs_graines_egalite():
    df = _metrics_df(expr=[0.01, 0.02], ent=[0.80, 0.79], std=[0.01, 0.01])
    sentence = ui.reading_sentence(df)
    assert "plus expressif" not in sentence
    assert "plus forte intrication" not in sentence
    assert sentence.count("indistinguables sur cette métrique") == 2


def test_phrase_de_lecture_moins_de_deux_circuits():
    assert ui.reading_sentence(_compare_df(with_std=False).iloc[0:0]) == ""
    assert ui.reading_sentence(_compare_df(with_std=False).iloc[0:1]) == ""


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


def test_phrases_en_notation_francaise():
    sentence = ui.reading_sentence(_metrics_df(expr=[0.01, 0.05], ent=[0.5, 0.9]))
    assert "0,0100" in sentence and "0.0100" not in sentence
    cost = _cost(36, 58)
    assert "×3,00" in ui.hardware_sentence(cost)


def test_schema_de_circuit_style_accepte_par_qiskit():
    import warnings

    from stochastiq import build_ansatz

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fig = ui.circuit_figure(build_ansatz("hardware_efficient", 4, 3))
    assert fig.get_facecolor()[:3] == (1.0, 1.0, 1.0)


def test_noms_d_affichage_des_ansatz():
    from stochastiq import list_ansatz

    assert [ui.ansatz_label(name) for name in list_ansatz()] == [
        "BasicEntangler",
        "StronglyEntangling",
        "HardwareEfficient",
        "RotationOnly",
        "AllToAll",
        "BrickWall",
        "DataReuploading",
    ]


def test_phrase_de_lecture_avec_noms_d_affichage():
    df = _metrics_df(expr=[0.01, 0.05], ent=[0.9, 0.6])
    df.index = ["all_to_all", "rotation_only"]
    sentence = ui.reading_sentence(df)
    assert "« AllToAll »" in sentence
    assert "all_to_all" not in sentence


def test_listes_deroulantes_en_noms_d_affichage():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert at.selectbox(key="diag_ansatz").value == "basic_entangler"
    assert at.selectbox(key="diag_ansatz").format_func("brick_wall") == "BrickWall"
    assert "HardwareEfficient" in at.multiselect(key="cmp_ansatz").options


def test_format_fraction():
    assert ui.format_fraction(1 / 3) == "33,3 %"
    assert ui.format_fraction(0) == "0,0 %"
    assert ui.format_fraction(math.nan) == "n/a"


def test_inactive_line():
    details = {
        "mean_variance": 0.02,
        "variance_per_parameter": np.zeros(36),
        "n_inactive_parameters": 12,
        "inactive_fraction": 12 / 36,
    }
    assert ui.inactive_line(details) == (
        "Paramètres inactifs (variance du gradient < 10⁻¹²) : 12 sur 36 (33,3 %)."
    )


def _pareto_df(expr, grad, std=False) -> pd.DataFrame:
    df = pd.DataFrame(
        {"expressibility": expr, "gradient_variance": grad},
        index=["all_to_all", "brick_wall", "rotation_only"][: len(expr)],
    )
    if std:
        df["expressibility_std"] = 0.001
        df["gradient_variance_std"] = 0.001
    return df


def test_phrase_pareto_un_seul_ansatz():
    # all_to_all est meilleur sur les deux critères.
    sentence = ui.pareto_sentence(_pareto_df([0.01, 0.03, 0.7], [0.05, 0.04, 0.03]))
    assert sentence.startswith("Le front de Pareto ne contient que « AllToAll ».")
    assert "un circuit du front n'est battu par aucun autre sur les deux critères" in sentence.lower()
    assert "BrickWall" not in sentence


def test_phrase_pareto_plusieurs_ansatz():
    sentence = ui.pareto_sentence(_pareto_df([0.01, 0.03, 0.7], [0.02, 0.04, 0.12]))
    assert "« AllToAll », « BrickWall » et « RotationOnly »" in sentence
    assert not any(ch.isdigit() for ch in sentence)


def test_figures_pareto_et_echelle():
    fig = ui.pareto_figure(_pareto_df([0.01, 0.03, 0.7], [0.05, 0.04, 0.03], std=True))
    ax = fig.axes[0]
    assert ax.get_xlabel() == "Expressibilité (plus bas = plus expressif)"
    assert ax.xaxis.get_major_formatter()(0.25, 0) == "0,25"
    results = {
        "hardware_efficient": pd.DataFrame({"n_qubits": [2, 3, 4], "mean_variance": [0.1, 0.05, 0.02]}),
        "data_reuploading": pd.DataFrame({"n_qubits": [2, 3, 4], "mean_variance": [0.08, 0.04, 0.03]}),
    }
    fig = ui.scaling_figure(results)
    ax = fig.axes[0]
    assert ax.get_yscale() == "log"
    assert [line.get_marker() for line in ax.get_lines()] == ["o", "s"]
    assert ax.yaxis.get_major_formatter()(0.01, 0) == "0,01"
    assert ax.yaxis.get_major_formatter()(1, 0) == "1"


def test_phrase_decroissance_nette():
    fit = {"factor_per_qubit": 0.5, "r2": 0.99, "n_points": 5}
    sentence = ui.scaling_sentence("hardware_efficient", fit)
    assert "la variance est multipliée par 0,50 à chaque qubit ajouté" in sentence
    assert "R² = 0,990" in sentence
    assert "plateau stérile" in sentence


@pytest.mark.parametrize(
    "fit",
    [
        {"factor_per_qubit": 0.9, "r2": 0.99, "n_points": 5},  # décroissance lente
        {"factor_per_qubit": 0.5, "r2": 0.6, "n_points": 5},  # ajustement médiocre
    ],
)
def test_phrase_decroissance_non_nette(fit):
    sentence = ui.scaling_sentence("data_reuploading", fit)
    assert "pas de décroissance exponentielle nette sur cette plage" in sentence
    assert "plateau stérile" not in sentence


def test_phrase_et_tableau_donnees_insuffisantes():
    fit = {"factor_per_qubit": None, "r2": None, "n_points": 2}
    assert "données insuffisantes" in ui.scaling_sentence("brick_wall", fit)
    table = ui.scaling_table({"brick_wall": fit, "all_to_all": {"factor_per_qubit": 0.71, "r2": 0.95, "n_points": 4}})
    assert table.index.tolist() == ["BrickWall", "AllToAll"]
    assert table["Facteur par qubit ajouté"].tolist() == ["données insuffisantes", "×0,71"]
    assert table["R²"].tolist() == ["n/a", "0,950"]
