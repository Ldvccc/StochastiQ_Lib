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
from matplotlib.ticker import FuncFormatter

SURFACE = "#F6F5FB"
CARD = "#FFFFFF"
TEXT = "#14163F"
TEXT_MUTED = "#585B7A"
VIOLET = "#5B4BFF"
CORAL = "#D42A45"
VIOLET_LIGHT = "#ECE9FF"

METRICS = ["expressibility", "entangling_capability", "gradient_variance"]

# Noms d'affichage des ansatz ; la bibliothèque garde les identifiants snake_case.
ANSATZ_LABELS = {
    "basic_entangler": "BasicEntangler",
    "strongly_entangling": "StronglyEntangling",
    "hardware_efficient": "HardwareEfficient",
    "rotation_only": "RotationOnly",
    "all_to_all": "AllToAll",
    "brick_wall": "BrickWall",
    "data_reuploading": "DataReuploading",
}

TOPOLOGY_LABELS = {
    "line": "Ligne",
    "ring": "Anneau",
    "full": "Complète",
    "heavy_hex": "Hexagone lourd",
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


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def format_fr(x: float, decimals: int) -> str:
    """Formate un nombre en notation française (virgule décimale).

    Retourne ``n/a`` si la valeur n'est pas définie.
    """
    if _is_missing(x):
        return "n/a"
    return f"{x:.{decimals}f}".replace(".", ",")


def format_value(value: float) -> str:
    """Formate une métrique : 4 décimales, virgule décimale.

    Une valeur non nulle qui s'afficherait 0,0000 passe en notation
    scientifique (``1,2000e-05``) pour ne pas être confondue avec zéro.
    """
    if _is_missing(value):
        return "n/a"
    if value != 0 and abs(value) < 5e-5:
        return f"{value:.4e}".replace(".", ",")
    return format_fr(value, 4)


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
    table.index = pd.Index([ansatz_label(name) for name in df.index], name="Ansatz")
    return table


def _metric_sentence(df: pd.DataFrame, metric: str, lower_is_better: bool, winner: str) -> str:
    """Phrase sur une métrique : gagnant si l'écart avec le deuxième est significatif."""
    ordered = df.sort_values(metric, ascending=lower_is_better)
    (name1, v1), (name2, v2) = list(ordered[metric].items())[:2]
    name1, name2 = ansatz_label(name1), ansatz_label(name2)
    gap = abs(v1 - v2)
    label = METRIC_LABELS[metric]

    std_column = f"{metric}_std"
    if std_column in df.columns:
        noise = ordered[std_column].iloc[0] + ordered[std_column].iloc[1]
        if gap <= noise:
            return (
                f"{label} : « {name1} » et « {name2} » sont indistinguables sur cette "
                f"métrique (écart {format_value(gap)}, inférieur à la somme des "
                f"écarts-types {format_value(noise)})."
            )
    elif gap <= 0.10 * abs(v1):
        return (
            f"{label} : les différences sont du même ordre que le bruit "
            "d'échantillonnage ; relancez avec plusieurs graines."
        )
    return winner.format(
        name1=name1, v1=format_value(v1), name2=name2, v2=format_value(v2)
    )


def reading_sentence(df: pd.DataFrame) -> str:
    """Rédige une phrase de lecture du tableau de ``compare``.

    Pour l'expressibilité et l'intrication, désigne le meilleur circuit
    seulement si son écart avec le deuxième est significatif :

    - une seule graine (pas de colonnes ``_std``) : écart supérieur à 10 % de
      la valeur du meilleur ; sinon, la phrase signale que les différences
      sont du même ordre que le bruit d'échantillonnage ;
    - plusieurs graines : écart supérieur à la somme des deux écarts-types ;
      sinon, la phrase indique que les circuits sont indistinguables.

    Retourne une chaîne vide s'il y a moins de deux circuits.
    """
    if len(df) < 2:
        return ""
    sentences = [
        _metric_sentence(
            df,
            "expressibility",
            lower_is_better=True,
            winner="Le circuit le plus expressif est « {name1} » "
            "(expressibilité {v1}, contre {v2} pour « {name2} »).",
        ),
        _metric_sentence(
            df,
            "entangling_capability",
            lower_is_better=False,
            winner="La plus forte intrication est obtenue par « {name1} » "
            "({v1}, contre {v2} pour « {name2} »).",
        ),
    ]
    if "expressibility_std" in df.columns:
        sentences.append("Valeurs moyennes sur les graines.")
    return " ".join(sentences)


LOW_SAMPLES_THRESHOLD = 1000

LOW_SAMPLES_WARNING = (
    "Avec moins de 1000 échantillons, l'expressibilité est surestimée. Comparez "
    "uniquement des résultats obtenus avec le même nombre d'échantillons."
)


def compare_params_line(n_samples: int, seed: int, n_seeds: int) -> str:
    """Rappelle les paramètres utilisés pour un calcul ``compare``."""
    seeds = "1 graine" if n_seeds == 1 else f"{n_seeds} graines"
    return f"Calcul effectué avec {n_samples} échantillons, graine {seed}, {seeds}."


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


def ansatz_label(name: str) -> str:
    """Retourne le nom d'affichage d'un ansatz de la bibliothèque."""
    return ANSATZ_LABELS.get(name, name)


def topology_label(topology: str) -> str:
    """Retourne le libellé français d'une topologie de la bibliothèque."""
    return TOPOLOGY_LABELS.get(topology, topology)


def hardware_table(cost: dict) -> pd.DataFrame:
    """Met en forme le résultat de ``hardware_cost`` sur ses trois niveaux de mesure."""
    levels = {
        "Circuit d'origine": cost["before"],
        "Après traduction": cost["basis_only"],
        "Après routage": cost["after"],
    }
    return pd.DataFrame(
        {
            column: [level["n_two_qubit_gates"], level["depth"]]
            for column, level in levels.items()
        },
        index=pd.Index(
            ["Portes à 2 qubits", "Profondeur"],
            name=f"Topologie : {topology_label(cost['topology'])}",
        ),
    )


def format_overhead(overhead: float) -> str:
    """Formate un surcoût (rapport de nombres de portes)."""
    if _is_missing(overhead):
        return "n/a"
    return f"×{format_fr(overhead, 2)}"


def hardware_sentence(cost: dict) -> str:
    """Rédige une phrase de lecture factuelle du résultat de ``hardware_cost``."""
    before, basis, after = cost["before"], cost["basis_only"], cost["after"]
    label = topology_label(cost["topology"])
    sentence = (
        f"Le circuit d'origine compte {before['n_two_qubit_gates']} portes à 2 qubits "
        f"pour une profondeur de {before['depth']}. La traduction vers les portes de base "
        f"donne {basis['n_two_qubit_gates']} portes à 2 qubits et une profondeur de "
        f"{basis['depth']}. "
    )
    if after["n_two_qubit_gates"] == basis["n_two_qubit_gates"]:
        sentence += (
            f"Sur la topologie {label}, le routage n'ajoute aucune porte à 2 qubits "
            f"(profondeur après routage : {after['depth']})."
        )
    else:
        sentence += (
            f"Sur la topologie {label}, le routage fait passer les portes à 2 qubits de "
            f"{basis['n_two_qubit_gates']} à {after['n_two_qubit_gates']} "
            f"({format_overhead(cost['routing_overhead_two_qubit'])}) et la profondeur de "
            f"{basis['depth']} à {after['depth']}."
        )
    return sentence


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


# Style du schéma de circuit (``QuantumCircuit.draw("mpl", style=...)``).
CIRCUIT_STYLE = {
    "backgroundcolor": CARD,
    "textcolor": TEXT,
    "linecolor": TEXT,
    "creglinecolor": TEXT_MUTED,
    "gatefacecolor": VIOLET,
    "gatetextcolor": CARD,
    "subtextcolor": CARD,
    "displaycolor": {
        "rx": [VIOLET, CARD],
        "ry": [VIOLET, CARD],
        "rz": [VIOLET, CARD],
        "cx": [TEXT, CARD],
        # Couleur du « + » de la cible (premier élément) : blanc sur disque #14163F.
        "target": [CARD, CARD],
    },
}


def circuit_figure(ansatz):
    """Dessine un circuit aux couleurs StochastiQ."""
    return ansatz.draw("mpl", style=CIRCUIT_STYLE)


# Graduations d'axe en notation française (virgule décimale).
FRENCH_TICKS = FuncFormatter(lambda value, _: f"{value:g}".replace(".", ","))


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
    ax.xaxis.set_major_formatter(FRENCH_TICKS)
    ax.yaxis.set_major_formatter(FRENCH_TICKS)
    ax.legend(frameon=False, labelcolor=TEXT)
    fig.tight_layout()
    return fig


def expressibility_figure(df: pd.DataFrame):
    """Barres de l'expressibilité par ansatz, avec barres d'erreur si disponibles."""
    fig, ax = _figure(height=3.2)
    yerr = df["expressibility_std"] if "expressibility_std" in df.columns else None
    ax.bar(
        [ansatz_label(name) for name in df.index],
        df["expressibility"],
        yerr=yerr,
        color=VIOLET,
        ecolor=TEXT,
        capsize=4,
    )
    ax.set_ylabel("Expressibilité (KL)")
    ax.yaxis.set_major_formatter(FRENCH_TICKS)
    ax.tick_params(axis="x", rotation=30)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    fig.tight_layout()
    return fig
