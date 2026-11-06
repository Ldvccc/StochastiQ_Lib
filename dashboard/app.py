"""Dashboard local StochastiQ : diagnostic de circuits.

Lancement : ``streamlit run dashboard/app.py``. Toutes les valeurs affichées
viennent de la bibliothèque ``stochastiq``.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

import ui  # noqa: E402
from stochastiq import (  # noqa: E402
    build_ansatz,
    circuit_stats,
    compare,
    entangling_capability,
    expressibility,
    fidelity_histogram,
    gradient_scaling,
    gradient_variance_details,
    hardware_cost,
    list_ansatz,
    list_topologies,
)

st.set_page_config(page_title="StochastiQ", layout="wide")
ui.inject_css()
ui.sidebar_brand()


@st.cache_data(show_spinner=False)
def run_diagnostic(name: str, n_qubits: int, layers: int, n_samples: int, seed: int) -> dict:
    ansatz = build_ansatz(name, n_qubits, layers)
    return {
        "expressibility": expressibility(ansatz, n_samples=n_samples, seed=seed),
        "entangling_capability": entangling_capability(ansatz, n_samples=n_samples, seed=seed),
        "gradient": gradient_variance_details(ansatz, n_samples=n_samples, seed=seed),
        "histogram": fidelity_histogram(ansatz, n_samples=n_samples, seed=seed),
    }


@st.cache_data(show_spinner=False)
def run_compare(
    names: tuple[str, ...], n_qubits: int, layers: int, n_samples: int, seed: int, n_seeds: int
):
    circuits = {name: build_ansatz(name, n_qubits, layers) for name in names}
    return compare(circuits, n_samples=n_samples, seed=seed, n_seeds=n_seeds)


@st.cache_data(show_spinner=False)
def run_stats(name: str, n_qubits: int, layers: int) -> dict:
    return circuit_stats(build_ansatz(name, n_qubits, layers))


@st.cache_data(show_spinner=False)
def run_hardware(name: str, n_qubits: int, layers: int, topology: str, seed: int) -> dict:
    return hardware_cost(build_ansatz(name, n_qubits, layers), topology=topology, seed=seed)


@st.cache_data(show_spinner=False)
def run_scaling(
    name: str,
    q_min: int,
    q_max: int,
    layers: int,
    layers_mode: str,
    n_samples: int,
    seed: int,
    observable: str,
):
    # La barre est créée et vidée dans la fonction : Streamlit rejoue ces
    # éléments lors d'un accès au cache, sans référence à un bloc extérieur.
    text = f"Étude en cours : {ui.ansatz_label(name)}, {ui.OBSERVABLE_LABELS[observable]}"
    bar = st.progress(0.0, text=text)
    df = gradient_scaling(
        name,
        range(q_min, q_max + 1),
        layers=layers,
        layers_mode=layers_mode,
        n_samples=n_samples,
        observable=observable,
        seed=seed,
        callback=lambda done, total: bar.progress(done / total, text=text),
    )
    bar.empty()
    return df


def circuit_inputs(prefix: str):
    """Choix commun de l'ansatz, du nombre de qubits et de couches."""
    c1, c2, c3 = st.columns(3)
    name = c1.selectbox(
        "Ansatz", list_ansatz(), format_func=ui.ansatz_label, key=f"{prefix}_ansatz"
    )
    n_qubits = c2.slider("Qubits", 2, 8, 4, key=f"{prefix}_qubits")
    layers = c3.slider("Couches", 1, 8, 3, key=f"{prefix}_layers")
    return name, n_qubits, layers


tab_diag, tab_compare, tab_ansatz, tab_hardware, tab_barren = st.tabs(
    ["Diagnostic", "Comparateur", "Ansatz", "Matériel", "Plateau stérile"]
)

with tab_diag:
    st.header("Diagnostic")
    name, n_qubits, layers = circuit_inputs("diag")
    c1, c2 = st.columns(2)
    n_samples = c1.number_input("Échantillons", 50, 5000, 500, step=50, key="diag_samples")
    seed = c2.number_input("Graine", 0, 1_000_000, 0, key="diag_seed")
    if n_samples < ui.LOW_SAMPLES_THRESHOLD:
        st.info(ui.LOW_SAMPLES_WARNING)

    if st.button("Diagnostiquer", type="primary", key="diag_run"):
        params = (name, n_qubits, layers, int(n_samples), int(seed))
        try:
            with st.spinner("Calcul en cours"):
                st.session_state["diagnostic"] = (params, run_diagnostic(*params))
        except ValueError as error:
            st.error(str(error))

    if "diagnostic" in st.session_state:
        params, result = st.session_state["diagnostic"]
        st.caption(
            f"{ui.ansatz_label(params[0])}, {params[1]} qubits, {params[2]} couches, "
            f"{params[3]} échantillons, graine {params[4]}."
        )
        cards = st.columns(3)
        cards[0].metric(
            "Expressibilité",
            ui.format_value(result["expressibility"]),
            help="Divergence KL avec la distribution de Haar. Plus bas = plus expressif.",
        )
        cards[1].metric(
            "Intrication",
            ui.format_value(result["entangling_capability"]),
            help="Mesure de Meyer-Wallach moyenne, entre 0 et 1.",
        )
        cards[2].metric(
            "Variance du gradient",
            ui.format_value(result["gradient"]["mean_variance"]),
            help="Variance du gradient moyennée sur tous les paramètres, coût ⟨Z₀⟩.",
        )
        st.caption(ui.inactive_line(result["gradient"]))
        st.subheader("Histogramme des fidélités")
        fig = ui.fidelity_figure(result["histogram"])
        st.pyplot(fig)
        plt.close(fig)
        ui.note(
            "Plus bas = plus expressif : l'expressibilité mesure l'écart entre "
            "l'histogramme du circuit et la référence de Haar."
        )

with tab_compare:
    st.header("Comparateur")
    names = st.multiselect(
        "Ansatz",
        list_ansatz(),
        default=list_ansatz(),
        format_func=ui.ansatz_label,
        key="cmp_ansatz",
    )
    c1, c2 = st.columns(2)
    cmp_qubits = c1.slider("Qubits", 2, 8, 4, key="cmp_qubits")
    cmp_layers = c2.slider("Couches", 1, 8, 3, key="cmp_layers")
    c3, c4, c5 = st.columns(3)
    cmp_samples = c3.number_input("Échantillons", 50, 5000, 300, step=50, key="cmp_samples")
    cmp_seed = c4.number_input("Graine", 0, 1_000_000, 0, key="cmp_seed")
    n_seeds = c5.slider("Nombre de graines", 1, 10, 1, key="cmp_n_seeds")
    if cmp_samples < ui.LOW_SAMPLES_THRESHOLD:
        st.info(ui.LOW_SAMPLES_WARNING)

    if st.button("Comparer", type="primary", key="cmp_run"):
        if not names:
            st.error("Sélectionnez au moins un ansatz.")
        else:
            params = (tuple(names), cmp_qubits, cmp_layers, int(cmp_samples), int(cmp_seed), n_seeds)
            try:
                with st.spinner("Calcul en cours"):
                    st.session_state["compare"] = (params, run_compare(*params))
            except ValueError as error:
                st.error(str(error))

    if "compare" in st.session_state:
        params, df = st.session_state["compare"]
        st.table(ui.compare_table(df))
        st.download_button(
            ui.CSV_LABEL,
            ui.to_csv(
                ui.compare_frame(df),
                {
                    "qubits": params[1],
                    "couches": params[2],
                    "échantillons": params[3],
                    "graine": params[4],
                    "graines": params[5],
                },
            ),
            file_name="comparaison.csv",
            mime="text/csv",
            key="cmp_csv",
        )
        st.caption(ui.compare_params_line(params[3], params[4], params[5]))
        st.markdown(ui.reading_sentence(df))
        st.subheader("Expressibilité et variance du gradient")
        fig = ui.pareto_figure(df)
        st.pyplot(fig)
        plt.close(fig)
        st.markdown(ui.pareto_sentence(df))
        ui.note(ui.PARETO_NOTE)
        fig = ui.expressibility_figure(df)
        st.pyplot(fig)
        plt.close(fig)
        ui.note("Plus bas = plus expressif.")

with tab_ansatz:
    st.header("Ansatz")
    name, n_qubits, layers = circuit_inputs("ans")
    try:
        ansatz = build_ansatz(name, n_qubits, layers)
        fig = ui.circuit_figure(ansatz)
        st.pyplot(fig)
        plt.close(fig)
        stats = run_stats(name, n_qubits, layers)
        c1, c2 = st.columns(2)
        c1.subheader("Caractéristiques")
        c1.table(ui.stats_table(stats))
        c2.subheader("Portes par type")
        c2.table(ui.gate_counts_table(stats))
    except ValueError as error:
        st.error(str(error))

with tab_hardware:
    st.header("Matériel")
    name, n_qubits, layers = circuit_inputs("hw")
    c1, c2 = st.columns(2)
    topology = c1.selectbox(
        "Topologie",
        list_topologies(),
        format_func=ui.topology_label,
        key="hw_topology",
    )
    hw_seed = c2.number_input("Graine du transpileur", 0, 1_000_000, 0, key="hw_seed")
    try:
        with st.spinner("Transpilation en cours"):
            cost = run_hardware(name, n_qubits, layers, topology, int(hw_seed))
        st.table(ui.hardware_table(cost))
        st.download_button(
            ui.CSV_LABEL,
            ui.to_csv(
                ui.hardware_frame(name, cost),
                {"qubits": n_qubits, "couches": layers, "graine": int(hw_seed)},
            ),
            file_name="materiel.csv",
            mime="text/csv",
            key="hw_csv",
        )
        st.metric(
            "Surcoût du routage",
            ui.format_overhead(cost["routing_overhead_two_qubit"]),
            help="Portes à 2 qubits après routage / après traduction vers les portes de base.",
        )
        st.markdown(ui.hardware_sentence(cost))
    except ValueError as error:
        st.error(str(error))
    ui.note(
        "Transpilation hors ligne avec Qiskit, vers les portes cx, rz, sx et x : "
        "aucune connexion à une vraie machine."
    )

with tab_barren:
    st.header("Plateau stérile")
    bp_names = st.multiselect(
        "Ansatz (4 au plus)",
        list_ansatz(),
        default=["hardware_efficient", "strongly_entangling", "data_reuploading"],
        format_func=ui.ansatz_label,
        max_selections=4,
        key="bp_ansatz",
    )
    c1, c2, c3 = st.columns(3)
    bp_qubits = c1.slider("Qubits (min et max)", 2, 8, (2, 6), key="bp_qubits")
    # Le mode est lu avant le curseur « Couches », qu'il désactive.
    bp_mode = c3.radio(
        "Mode de couches",
        list(ui.LAYERS_MODE_LABELS),
        format_func=ui.LAYERS_MODE_LABELS.get,
        key="bp_mode",
    )
    # Désactivé, le curseur reste affiché : sa valeur est conservée dans
    # st.session_state["bp_layers"] et réapparaît en repassant en mode « Fixe ».
    bp_layers = c2.slider(
        "Couches", 1, 8, 3, key="bp_layers", disabled=bp_mode == "linear"
    )
    if bp_mode == "linear":
        c2.caption(ui.PROPORTIONAL_LAYERS_NOTE)
    c4, c5 = st.columns(2)
    bp_samples = c4.number_input("Échantillons", 10, 2000, 100, step=10, key="bp_samples")
    bp_seed = c5.number_input("Graine", 0, 1_000_000, 0, key="bp_seed")
    c6, c7 = st.columns(2)
    # La case est lue avant l'observable, qu'elle rend sans objet.
    bp_compare = c7.checkbox(ui.COMPARE_OBSERVABLES_LABEL, key="bp_compare")
    bp_observable = c6.radio(
        "Observable",
        list(ui.OBSERVABLE_LABELS),
        format_func=ui.OBSERVABLE_LABELS.get,
        key="bp_observable",
        horizontal=True,
        disabled=bp_compare,
    )
    if bp_qubits[1] > 6:
        st.info("Plage au-delà de 6 qubits : calcul plus long.")

    if st.button("Lancer l'étude", type="primary", key="bp_run"):
        if not bp_names:
            st.error("Sélectionnez au moins un ansatz.")
        else:
            try:
                st.session_state["barren_layers"] = (bp_mode, bp_layers)
                st.session_state["barren_params"] = {
                    "qubits": f"{bp_qubits[0]}-{bp_qubits[1]}",
                    "couches": bp_layers if bp_mode == "fixed" else "nombre de qubits",
                    "mode": bp_mode,
                    "échantillons": int(bp_samples),
                    "graine": int(bp_seed),
                    "observable": "Z0+Zall" if bp_compare else bp_observable,
                }
                observables = ["Z0", "Zall"] if bp_compare else [bp_observable]
                st.session_state["barren_compare"] = bp_compare
                st.session_state["barren"] = {
                    observable: {
                        bp_name: run_scaling(
                            bp_name,
                            bp_qubits[0],
                            bp_qubits[1],
                            bp_layers,
                            bp_mode,
                            int(bp_samples),
                            int(bp_seed),
                            observable,
                        )
                        for bp_name in bp_names
                    }
                    for observable in observables
                }
            except ValueError as error:
                st.error(str(error))

    if "barren" in st.session_state:
        by_observable = st.session_state["barren"]
        if st.session_state["barren_compare"]:
            fig = ui.observables_figure(by_observable["Z0"], by_observable["Zall"])
            summary = ui.observables_summary(by_observable["Z0"], by_observable["Zall"])
            table = ui.observables_table(summary)
            sentences = [ui.observables_sentence(n, e) for n, e in summary.items()]
            note = ui.observable_note(None)
        else:
            observable, results = next(iter(by_observable.items()))
            fig = ui.scaling_figure(results)
            summary = ui.scaling_summary(results)
            table = ui.scaling_table(summary)
            sentences = [ui.scaling_sentence(n, e) for n, e in summary.items()]
            note = ui.observable_note(observable)
        st.pyplot(fig)
        plt.close(fig)
        st.table(table)
        st.download_button(
            ui.CSV_LABEL,
            ui.to_csv(ui.observables_frame(by_observable), st.session_state["barren_params"]),
            file_name="plateau_sterile.csv",
            mime="text/csv",
            key="bp_csv",
        )
        lines = [ui.layers_line(*st.session_state["barren_layers"]), *sentences]
        st.markdown("  \n".join(lines))
        ui.note(note)
