"""Style et petits composants du dashboard StochastiQ.

Les fonctions de préparation (tableaux, phrase de lecture, formatage) sont
pures et testables ; elles ne font que mettre en forme des valeurs produites
par la bibliothèque ``stochastiq``.
"""

import math

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

SURFACE = "#F6F5FB"
CARD = "#FFFFFF"
TEXT = "#14163F"
TEXT_MUTED = "#585B7A"
VIOLET = "#5B4BFF"
CORAL = "#D42A45"
VIOLET_LIGHT = "#ECE9FF"

METRICS = ["expressibility", "entangling_capability", "gradient_variance"]

TOPOLOGY_LABELS = {
    "line": "Ligne",
    "ring": "Anneau",
    "full": "Complète",
    "heavy_hex": "Heavy-hex (19 qubits)",
}

METRIC_LABELS = {
    "n_qubits": "Qubits",
    "n_parameters": "Paramètres",
    "depth": "Profondeur",
    "n_two_qubit_gates": "Portes à 2 qubits",
    "expressibility": "Expressibilité",
    "entangling_capability": "Intrication",
    "gradient_variance": "Variance du gradient",
}

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700&display=swap');

html, body, .stApp, .stMarkdown p, label, li, .stCaption {{
    font-family: 'Instrument Sans', sans-serif;
    color: {TEXT};
}}
h1, h2, h3, h4, .sq-brand {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: {TEXT};
}}
.sq-brand {{
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.1;
}}
.sq-brand span {{
    color: {VIOLET};
}}
.sq-subtitle, .sq-note {{
    color: {TEXT_MUTED};
    font-size: 0.9rem;
}}
[data-testid="stMetric"] {{
    background: {CARD};
    border: 1px solid {VIOLET_LIGHT};
    border-radius: 12px;
    padding: 16px 20px;
}}
[data-testid="stMetricLabel"] p {{
    color: {TEXT_MUTED};
}}
[data-testid="stMetricValue"], .stTable td, code {{
    font-family: 'JetBrains Mono', monospace;
}}
.stTable table {{
    background: {CARD};
}}
</style>
"""


# Fonctions pures


def format_value(value: float) -> str:
    """Formate une valeur numérique pour l'affichage (``n/a`` si non définie)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    if value != 0 and abs(value) < 1e-3:
        return f"{value:.3e}"
    return f"{value:.4f}"


def compare_table(df: pd.DataFrame) -> pd.DataFrame:
    """Prépare le tableau de ``compare`` pour l'affichage.

    Les métriques sont formatées, au format « moyenne ± écart-type » quand
    les colonnes ``<nom>_std`` sont présentes. Les colonnes sont renommées en
    français ; l'ordre des lignes est conservé.
    """
    table = pd.DataFrame(index=df.index)
    for column in ["n_qubits", "n_parameters", "depth", "n_two_qubit_gates"]:
        table[METRIC_LABELS[column]] = df[column].astype(int)
    for metric in METRICS:
        if f"{metric}_std" in df.columns:
            table[METRIC_LABELS[metric]] = [
                f"{format_value(m)} ± {format_value(s)}"
                for m, s in zip(df[metric], df[f"{metric}_std"])
            ]
        else:
            table[METRIC_LABELS[metric]] = [format_value(m) for m in df[metric]]
    table.index.name = "Ansatz"
    return table


def _names(names: list[str]) -> str:
    quoted = [f"« {name} »" for name in names]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + " et " + quoted[-1]


def reading_sentence(df: pd.DataFrame) -> str:
    """Rédige une phrase de lecture du tableau de ``compare``.

    Cite le ou les circuits les plus expressifs (expressibilité minimale) et
    ceux qui ont la plus forte intrication, avec leurs valeurs. Les ex aequo
    sont tous cités. Retourne une chaîne vide si le tableau est vide.
    """
    if df.empty:
        return ""
    averaged = "expressibility_std" in df.columns

    expr = df["expressibility"]
    best_expr = [name for name, v in expr.items() if np.isclose(v, expr.min())]
    ent = df["entangling_capability"]
    best_ent = [name for name, v in ent.items() if np.isclose(v, ent.max())]

    if len(best_expr) == 1:
        first = f"Le circuit le plus expressif est {_names(best_expr)}"
    else:
        first = f"Les circuits les plus expressifs sont {_names(best_expr)}"
    first += f" (expressibilité {format_value(expr.min())})."

    if len(best_ent) == 1:
        second = f"La plus forte intrication est obtenue par {_names(best_ent)}"
    else:
        second = f"La plus forte intrication est obtenue par {_names(best_ent)}, ex aequo"
    second += f" ({format_value(ent.max())})."

    sentence = f"{first} {second}"
    if averaged:
        sentence += " Valeurs moyennes sur les graines."
    return sentence


def stats_table(stats: dict) -> pd.DataFrame:
    """Met en forme le résultat de ``circuit_stats`` (hors détail des portes)."""
    keys = ["n_qubits", "n_parameters", "depth", "n_two_qubit_gates"]
    return pd.DataFrame(
        {"Valeur": [int(stats[k]) for k in keys]},
        index=pd.Index([METRIC_LABELS[k] for k in keys], name="Caractéristique"),
    )


def gate_counts_table(stats: dict) -> pd.DataFrame:
    """Met en forme le nombre de portes par type de ``circuit_stats``."""
    counts = sorted(stats["gate_counts"].items(), key=lambda item: (-item[1], item[0]))
    return pd.DataFrame(
        {"Nombre": [n for _, n in counts]},
        index=pd.Index([name for name, _ in counts], name="Porte"),
    )


def hardware_table(cost: dict) -> pd.DataFrame:
    """Met en forme le résultat de ``hardware_cost`` en tableau avant / après."""
    return pd.DataFrame(
        {
            "Avant": [cost["n_two_qubit_gates_before"], cost["depth_before"]],
            "Après": [cost["n_two_qubit_gates_after"], cost["depth_after"]],
        },
        index=pd.Index(["Portes à 2 qubits", "Profondeur"], name=f"Topologie {cost['topology']}"),
    )


def format_overhead(overhead: float) -> str:
    """Formate le surcoût en portes à 2 qubits (rapport après / avant)."""
    if overhead is None or math.isnan(overhead):
        return "n/a"
    return f"×{overhead:.2f}"


# Composants graphiques


def inject_css() -> None:
    """Injecte les polices et le style StochastiQ."""
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_brand() -> None:
    """Affiche le nom et le sous-titre dans la barre latérale."""
    st.sidebar.markdown(
        '<div class="sq-brand">Stochasti<span>Q</span></div>'
        '<div class="sq-subtitle">Diagnostic de circuits</div>',
        unsafe_allow_html=True,
    )


def note(text: str) -> None:
    """Affiche une note en texte secondaire."""
    st.markdown(f'<p class="sq-note">{text}</p>', unsafe_allow_html=True)


def _style_axes(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT_MUTED)
        ax.spines[side].set_linewidth(0.6)
    ax.tick_params(colors=TEXT_MUTED, labelsize=9, length=3, width=0.6)
    ax.xaxis.label.set_color(TEXT_MUTED)
    ax.yaxis.label.set_color(TEXT_MUTED)
    ax.set_facecolor(CARD)


def _figure(width: float = 7, height: float = 3.4):
    fig, ax = plt.subplots(figsize=(width, height))
    fig.patch.set_facecolor(CARD)
    _style_axes(ax)
    return fig, ax


def fidelity_figure(histogram: dict):
    """Histogramme des fidélités (barres violettes) et référence de Haar (corail)."""
    edges = histogram["edges"]
    centers = (edges[:-1] + edges[1:]) / 2
    fig, ax = _figure()
    ax.bar(
        centers,
        histogram["circuit"],
        width=np.diff(edges),
        color=VIOLET,
        alpha=0.85,
        label="Circuit",
    )
    ax.plot(centers, histogram["haar"], color=CORAL, linewidth=2, label="Haar")
    ax.set_xlabel("Fidélité")
    ax.set_ylabel("Probabilité")
    ax.set_xlim(0, 1)
    ax.legend(frameon=False, labelcolor=TEXT)
    fig.tight_layout()
    return fig


def expressibility_figure(df: pd.DataFrame):
    """Barres de l'expressibilité par ansatz, avec barres d'erreur si disponibles."""
    fig, ax = _figure(height=3.2)
    yerr = df["expressibility_std"] if "expressibility_std" in df.columns else None
    ax.bar(
        df.index.astype(str),
        df["expressibility"],
        yerr=yerr,
        color=VIOLET,
        ecolor=TEXT,
        capsize=4,
    )
    ax.set_ylabel("Expressibilité (KL)")
    ax.tick_params(axis="x", rotation=30)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    fig.tight_layout()
    return fig
