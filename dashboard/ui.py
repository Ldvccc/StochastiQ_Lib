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
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from stochastiq import pareto_front

SURFACE = "#F6F5FB"
CARD = "#FFFFFF"
TEXT = "#14163F"
TEXT_MUTED = "#585B7A"
VIOLET = "#5B4BFF"
CORAL = "#D42A45"
VIOLET_LIGHT = "#ECE9FF"
LINE = "#E1DFEE"

METRICS = ["expressibility", "entangling_capability", "gradient_variance", "gradient_variance_active"]

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
    "gradient_variance_active": "Variance du gradient (actifs)",
    "inactive_fraction": "Paramètres inactifs",
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
    """Formate une métrique : 4 décimales, virgule décimale, sans notation scientifique."""
    return format_fr(value, 4)


def inactive_line(details: dict) -> str:
    """Résume les paramètres inactifs d'un résultat ``gradient_variance_details``."""
    n_inactive = details["n_inactive_parameters"]
    n_params = len(details["variance_per_parameter"])
    return (
        f"Paramètres inactifs (variance du gradient < 10⁻¹²) : {n_inactive} sur "
        f"{n_params} ({format_fraction(details['inactive_fraction'])})."
    )


def format_fraction(value: float) -> str:
    """Formate une proportion entre 0 et 1 en pourcentage (``33,3 %``)."""
    if _is_missing(value):
        return "n/a"
    return f"{format_fr(100 * value, 1)} %"


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
    table[METRIC_LABELS["inactive_fraction"]] = [format_fraction(f) for f in df["inactive_fraction"]]
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


def pareto_mask(df: pd.DataFrame) -> list[bool]:
    """Front de Pareto du tableau ``compare`` : expressibilité basse, variance du gradient haute."""
    points = list(zip(df["expressibility"], df["gradient_variance"]))
    return pareto_front(points, minimize_x=True, maximize_y=True)


def pareto_sentence(df: pd.DataFrame) -> str:
    """Rédige la phrase de lecture du nuage expressibilité / variance du gradient."""
    if df.empty:
        return ""
    names = [ansatz_label(name) for name, on_front in zip(df.index, pareto_mask(df)) if on_front]
    quoted = [f"« {name} »" for name in names]
    if len(quoted) == 1:
        first = f"Le front de Pareto ne contient que {quoted[0]}."
    else:
        listed = ", ".join(quoted[:-1]) + " et " + quoted[-1]
        first = f"Le front de Pareto contient {listed}."
    return (
        f"{first} Un circuit du front n'est battu par aucun autre sur les deux critères "
        "(expressibilité plus basse et variance du gradient plus élevée)."
    )


LAYERS_MODE_LABELS = {"fixed": "Fixe", "linear": "Proportionnel aux qubits"}

PROPORTIONAL_LAYERS_NOTE = (
    "En mode proportionnel, le nombre de couches est égal au nombre de qubits."
)


def layers_line(layers_mode: str, layers: int) -> str:
    """Rappelle le nombre de couches utilisé pour une étude ``gradient_scaling``."""
    if layers_mode == "linear":
        return "Couches : égales au nombre de qubits."
    return f"Couches : {layers} (fixe)."

# Seuils au-delà desquels la décroissance est qualifiée de plateau stérile.
BARREN_FACTOR = 0.8
BARREN_R2 = 0.9


def format_factor(fit: dict) -> str:
    """Formate le facteur par qubit ajouté d'un résultat ``fit_decay``."""
    if fit["factor_per_qubit"] is None:
        return "données insuffisantes"
    return format_overhead(fit["factor_per_qubit"])


def scaling_table(fits: dict[str, dict]) -> pd.DataFrame:
    """Tableau des ajustements ``fit_decay`` par ansatz."""
    return pd.DataFrame(
        {
            "Facteur par qubit ajouté": [format_factor(fit) for fit in fits.values()],
            "R²": [
                "n/a" if fit["r2"] is None else format_fr(fit["r2"], 3) for fit in fits.values()
            ],
        },
        index=pd.Index([ansatz_label(name) for name in fits], name="Ansatz"),
    )


def scaling_sentence(name: str, fit: dict) -> str:
    """Phrase de lecture factuelle d'un ajustement ``fit_decay``.

    Le terme « plateau stérile » n'est employé que si le facteur par qubit
    est inférieur à 0,8 avec un R² supérieur à 0,9.
    """
    label = f"« {ansatz_label(name)} »"
    factor, r2 = fit["factor_per_qubit"], fit["r2"]
    if factor is None:
        return (
            f"{label} : données insuffisantes pour un ajustement "
            f"({fit['n_points']} point(s) valide(s), 3 nécessaires)."
        )
    sentence = (
        f"{label} : la variance est multipliée par {format_fr(factor, 2)} à chaque qubit "
        f"ajouté (ajustement exponentiel, R² = {format_fr(r2, 3)})"
    )
    if factor < BARREN_FACTOR and r2 > BARREN_R2:
        return sentence + " ; décroissance exponentielle nette, signe d'un plateau stérile."
    return sentence + " ; pas de décroissance exponentielle nette sur cette plage."


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


def log_ticks(vmin: float, vmax: float) -> list[float]:
    """Puissances de dix à graduer sur un axe logarithmique couvrant [vmin, vmax].

    Retourne les puissances de dix comprises dans la plage, étendue d'une
    décade (du côté le plus proche des données) tant qu'il y a moins de
    deux graduations. Le résultat contient donc toujours au moins deux
    puissances de dix consécutives.

    Lève
    ----
    ValueError
        Si ``vmin`` ou ``vmax`` est négatif ou nul (un axe logarithmique ne
        peut pas les représenter : filtrer ces valeurs avant l'appel), ou si
        ``vmin > vmax``.
    """
    if vmin <= 0 or vmax <= 0:
        raise ValueError("log_ticks attend des valeurs strictement positives.")
    if vmin > vmax:
        raise ValueError("log_ticks attend vmin <= vmax.")
    # Tolérance pour que 0,01 soit bien reconnue comme 10^-2.
    lo_log, hi_log = math.log10(vmin), math.log10(vmax)
    lo, hi = math.ceil(lo_log - 1e-9), math.floor(hi_log + 1e-9)
    while hi - lo + 1 < 2:
        # Écart (en décades) des données à la puissance de dix inférieure / supérieure.
        gap_below = lo_log - (lo - 1)
        gap_above = (hi + 1) - hi_log
        if gap_below <= gap_above:
            lo -= 1
        else:
            hi += 1
    return [10.0**k for k in range(lo, hi + 1)]


def _log_tick(value: float, _=None) -> str:
    """Étiquette française d'une graduation logarithmique (« 0,01 », « 1,5e-5 »)."""
    if value <= 0:
        return ""
    exponent = math.floor(math.log10(value) + 1e-9)
    if value < 1e-4:
        mantissa = f"{value / 10**exponent:.2g}".replace(".", ",")
        return f"{mantissa}e{exponent}"
    return format_fr(value, max(0, -exponent))


# Graduations d'un axe logarithmique, en écriture décimale française.
FRENCH_LOG_TICKS = FuncFormatter(_log_tick)

LOG_NUMTICKS = 50


def pareto_figure(df: pd.DataFrame):
    """Nuage expressibilité / variance moyenne du gradient, front de Pareto en violet plein."""
    fig, ax = _figure(height=3.8)
    on_front = np.array(pareto_mask(df))
    x, y = df["expressibility"].to_numpy(), df["gradient_variance"].to_numpy()
    if "expressibility_std" in df.columns:
        ax.errorbar(
            x,
            y,
            xerr=df["expressibility_std"],
            yerr=df["gradient_variance_std"],
            fmt="none",
            ecolor=TEXT_MUTED,
            elinewidth=0.8,
            capsize=3,
            zorder=1,
        )
    for mask, face, label in [(on_front, VIOLET, "Front de Pareto"), (~on_front, VIOLET_LIGHT, "Autres")]:
        if mask.any():
            ax.scatter(
                x[mask], y[mask], s=60, color=face, edgecolors=VIOLET, linewidths=1.2,
                label=label, zorder=2,
            )
    for name, xi, yi in zip(df.index, x, y):
        ax.annotate(
            ansatz_label(name), (xi, yi), xytext=(6, 4), textcoords="offset points",
            fontsize=8, color=TEXT,
        )
    ax.set_xlabel("Expressibilité (plus bas = plus expressif)")
    ax.set_ylabel("Variance moyenne du gradient")
    ax.xaxis.set_major_formatter(FRENCH_TICKS)
    ax.yaxis.set_major_formatter(FRENCH_TICKS)
    ax.legend(frameon=False, fontsize=8, labelcolor=TEXT_MUTED)
    fig.tight_layout()
    return fig


# Une couleur et un marqueur par courbe, pour ne pas distinguer par la seule couleur.
SCALING_STYLES = [(VIOLET, "o"), (TEXT, "s"), (CORAL, "^"), (TEXT_MUTED, "D")]


def scaling_figure(results: dict[str, pd.DataFrame]):
    """Variance moyenne du gradient en fonction du nombre de qubits, échelle log."""
    fig, ax = _figure(height=3.6)
    positive = []
    for (name, df), (color, marker) in zip(results.items(), SCALING_STYLES):
        valid = df["mean_variance"] > 0
        positive.extend(df.loc[valid, "mean_variance"])
        ax.plot(
            df.loc[valid, "n_qubits"], df.loc[valid, "mean_variance"], color=color,
            marker=marker, linewidth=1.6, markersize=6, label=ansatz_label(name),
        )
    ax.set_yscale("log")
    ax.set_xlabel("Nombre de qubits")
    ax.set_ylabel("Variance moyenne du gradient")
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(FRENCH_TICKS)
    if positive:
        ticks = log_ticks(min(positive), max(positive))
        # Marge de 15 % pour ne pas couper les marqueurs aux extrémités.
        ax.set_ylim(min(ticks[0], min(positive)) / 1.15, max(ticks[-1], max(positive)) * 1.15)
        # numticks large : au-dessous du nombre de décades visibles, LogLocator
        # saute des puissances de dix et supprime les graduations mineures.
        ax.yaxis.set_major_locator(LogLocator(base=10, numticks=LOG_NUMTICKS))
        ax.yaxis.set_minor_locator(LogLocator(base=10, subs=range(2, 10), numticks=LOG_NUMTICKS))
    ax.yaxis.set_major_formatter(FRENCH_LOG_TICKS)
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.grid(True, which="major", axis="y", color=LINE, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, labelcolor=TEXT_MUTED)
    fig.tight_layout()
    return fig
