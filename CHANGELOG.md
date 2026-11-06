# Historique des versions

## 0.1.0 (2026-11-06)

Première version du prototype.

### Ansatz
- Les 7 ansatz de QCBM Lab, reconstruits d'après le rapport du projet (section 2.4) : `basic_entangler`, `strongly_entangling`, `hardware_efficient`, `rotation_only`, `all_to_all`, `brick_wall`, `data_reuploading` (`build_ansatz`, `list_ansatz`).
- Vérification contre PennyLane (option `verify`) : gabarits `BasicEntanglerLayers` et `StronglyEntanglingLayers`, et circuits de référence en portes PennyLane pour les autres.

### Métriques
- Expressibilité de Sim et al. (2019) et histogramme des fidélités comparé à la référence de Haar (`expressibility`, `fidelity_histogram`).
- Capacité d'intrication de Meyer-Wallach (`entangling_capability`).
- Variance du gradient par la règle du décalage de paramètre, calculée pour chaque paramètre, avec les observables `Z0` et `Zmean`. Sorties : moyenne sur tous les paramètres, moyenne sur les paramètres actifs, part des paramètres inactifs (`gradient_variance`, `gradient_variance_details`).
- Statistiques de circuit : profondeur, portes à 2 qubits, portes par type (`circuit_stats`).
- Comparaison de plusieurs ansatz en `pandas.DataFrame`, avec moyenne et écart-type sur plusieurs graines (`compare`). Front de Pareto (`pareto_front`).

### Coût matériel
- Transpilation hors ligne sur les topologies ligne, anneau, complète et heavy-hex (`hardware_cost`, `list_topologies`). Trois niveaux de mesure (circuit d'origine, traduction vers les portes de base, routage) et surcoût du routage isolé.

### Plateau stérile
- Variance du gradient en fonction du nombre de qubits, à profondeur fixe ou proportionnelle (`gradient_scaling`). Ajustement exponentiel avec facteur par qubit et R² (`fit_decay`).

### Dashboard
- Dashboard Streamlit local (`streamlit run dashboard/app.py`), en français, aux couleurs StochastiQ. Cinq onglets : Diagnostic, Comparateur (avec le nuage de Pareto), Ansatz, Matériel et Plateau stérile.
- Phrases de lecture générées à partir des chiffres, avec des seuils explicites. Avertissement sous 1000 échantillons, virgule décimale, export CSV des tableaux.

### Documentation
- `README.md`, `docs/METRIQUES.md` et le notebook `examples/demo.ipynb`.
