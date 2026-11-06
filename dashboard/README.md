# Dashboard StochastiQ

Dashboard local de diagnostic de circuits, construit avec Streamlit. Il n'appelle que la bibliothèque `stochastiq` : toutes les valeurs affichées en viennent.

## Lancement

Depuis la racine du dépôt :

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

## Onglets

- **Diagnostic** : expressibilité, intrication et variance du gradient d'un ansatz, avec l'histogramme des fidélités comparé à la référence de Haar.
- **Comparateur** : tableau `compare(...)` sur plusieurs ansatz, avec moyenne ± écart-type quand plusieurs graines sont utilisées, et nuage expressibilité / variance du gradient (paramètres actifs) avec son front de Pareto.
- **Ansatz** : dessin du circuit, caractéristiques et nombre de portes par type.
- **Matériel** : coût de transpilation hors ligne sur une topologie (ligne, anneau, complète, hexagone lourd), sans connexion à une vraie machine.
- **Plateau stérile** : variance du gradient en fonction du nombre de qubits (paramètres actifs et tous les paramètres), ajustement exponentiel et phrase de lecture.

Sous les tableaux du Comparateur, du Matériel et du Plateau stérile, le bouton « Télécharger en CSV » exporte les valeurs brutes. Le fichier est en UTF-8, avec virgule séparatrice, point décimal et noms de colonnes de la bibliothèque. Sa première ligne, commençant par `#`, rappelle les paramètres et la version du paquet. Pour le relire : `pandas.read_csv(fichier, comment="#")`.

## Fichiers

- `app.py` : mise en page et appels à la bibliothèque.
- `ui.py` : style, graphiques et fonctions pures de mise en forme (testées dans `tests/test_dashboard.py`).
- `../.streamlit/config.toml` : thème.
