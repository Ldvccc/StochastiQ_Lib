# StochastiQ

`stochastiq` est un prototype de diagnostic d'ansatz Qiskit pour les machines de Born quantiques (QCBM). Il mesure l'expressibilité, l'intrication et la variance du gradient d'un circuit paramétré, ainsi que son coût de transpilation sur quelques topologies matérielles. Un dashboard Streamlit local permet de comparer les 7 ansatz du projet QCBM Lab et d'étudier l'apparition de plateaux stériles.

## Installation

Python 3.10 ou plus récent. Depuis la racine du dépôt :

```bash
pip install -e ".[dev,dashboard,examples]"
pytest
```

Options : `dev` (pytest), `dashboard` (Streamlit, matplotlib, pylatexenc), `examples` (matplotlib, Jupyter), `verify` (PennyLane, pour vérifier les ansatz contre ses gabarits).

Depuis GitHub, bibliothèque seule :

```bash
pip install "git+https://github.com/Ldvccc/StochastiQ_Lib.git"
```

## Démarrage rapide

```python
from stochastiq import build_ansatz, expressibility, gradient_variance_details

qc = build_ansatz("hardware_efficient", n_qubits=4, layers=3)
print(expressibility(qc, n_samples=1000, seed=0))  # plus bas = plus expressif
print(gradient_variance_details(qc, seed=0)["active_mean_variance"])
```

Pour comparer plusieurs ansatz : `compare({nom: circuit}, n_samples=1000, seed=0, n_seeds=3)`, qui retourne un `pandas.DataFrame`. Pour une étude en fonction du nombre de qubits : `gradient_scaling(nom, range(2, 7))` et `fit_decay`. Pour le coût matériel : `hardware_cost(circuit, topology="heavy_hex", seed=0)`. Le notebook [`examples/demo.ipynb`](examples/demo.ipynb) enchaîne ces appels.

## Dashboard

```bash
streamlit run dashboard/app.py
```

Il compte cinq onglets : Diagnostic, Comparateur, Ansatz, Matériel et Plateau stérile. Chaque tableau s'exporte en CSV. Voir [`dashboard/README.md`](dashboard/README.md).

## Les 7 ansatz

Définis d'après le rapport QCBM Lab, section 2.4 (détails dans la docstring de [`src/stochastiq/ansatz.py`](src/stochastiq/ansatz.py)). Les colonnes donnent le cas général pour n qubits et L couches :

| Nom (`build_ansatz`) | Affichage | Rotations par qubit | Entangleurs par couche | Paramètres | CNOT |
|---|---|---|---|---|---|
| `basic_entangler` | BasicEntangler | RX | anneau i → i+1 (un seul CNOT si n = 2) | L·n | n·L (L si n = 2) |
| `strongly_entangling` | StronglyEntangling | RZ, RY, RZ | i → i+r, r = (l mod (n−1)) + 1 | 3·L·n | n·L |
| `hardware_efficient` | HardwareEfficient | RY, RZ | chaîne i → i+1 | 2·L·n | (n−1)·L |
| `rotation_only` | RotationOnly | RY | aucun | L·n | 0 |
| `all_to_all` | AllToAll | RX, RY, RZ | toutes les paires i < j | 3·L·n | n(n−1)/2 · L |
| `brick_wall` | BrickWall | RY, RZ | paires paires, puis impaires en alternance | 2·L·n | ⌊n/2⌋ (couche paire), ⌊(n−1)/2⌋ (couche impaire) |
| `data_reuploading` | DataReuploading | RZ, RY, RZ | anneau i → i+1 | 3·L·n | n·L |

## Métriques

Les définitions précises, avec leurs formules et leurs références (Sim et al. 2019, arXiv:1905.10876), sont dans [`docs/METRIQUES.md`](docs/METRIQUES.md) :
- expressibilité ;
- intrication de Meyer-Wallach ;
- variance du gradient (règle du décalage de paramètre), paramètres inactifs ;
- ajustement exponentiel ;
- front de Pareto ;
- coût matériel.

## Limites connues

- **Biais d'échantillonnage** : l'expressibilité est surestimée avec peu d'échantillons. Ne comparez que des valeurs obtenues avec le même nombre d'échantillons.
- **Observable** : la variance du gradient est calculée par défaut sur l'observable locale Z0. Ses conclusions dépendent de l'observable et du nombre de couches.
- **Simulation** : elle est exacte et sans bruit. Aucun modèle d'erreur matérielle n'est appliqué.
- **Transpilation** : elle se fait hors ligne et repose sur des heuristiques de placement et de routage. Le coût matériel dépend de la graine du transpileur.
- **Portée des métriques** : aucun lien n'est démontré ici entre ces métriques et la qualité d'apprentissage d'une QCBM.
- **Ansatz** : les 7 ansatz sont reconstruits d'après le rapport du projet. Ils sont vérifiés contre PennyLane si l'option `verify` est installée, mais pas contre le code d'origine de QCBM Lab.

## Hors périmètre de ce prototype

- Entraînement de QCBM.
- Connexion à de vraies machines (IBM, Origin).
- Interface web multi-utilisateurs.
- Gestion d'équipe.

## Citer ce travail

StochastiQ, paquet `stochastiq` version 0.1.0, dépôt StochastiQ_Lib : https://github.com/Ldvccc/StochastiQ_Lib.

## Licence

MIT, voir [`LICENSE`](LICENSE). Les évolutions sont listées dans [`CHANGELOG.md`](CHANGELOG.md).
