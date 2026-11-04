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
- **Comparateur** : tableau `compare(...)` sur plusieurs ansatz, avec moyenne ± écart-type quand plusieurs graines sont utilisées.
- **Ansatz** : dessin du circuit, caractéristiques et nombre de portes par type.
- **Matériel** : coût de transpilation hors ligne sur une topologie (ligne, anneau, complète, heavy-hex), sans connexion à une vraie machine.

## Fichiers

- `app.py` : mise en page et appels à la bibliothèque.
- `ui.py` : style, graphiques et fonctions pures de mise en forme (testées dans `tests/test_dashboard.py`).
- `../.streamlit/config.toml` : thème.
