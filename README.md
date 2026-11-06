# StochastiQ

StochastiQ est un prototype de diagnostic d'ansatz Qiskit pour les machines de Born quantiques (QCBM). Il mesure l'expressibilité, l'intrication et la variance du gradient d'un circuit paramétré, ainsi que son coût de transpilation sur quelques topologies matérielles. Une API et une application web permettent à une petite équipe de lancer ces diagnostics, de les commenter et de suivre l'activité d'un projet.

**Prototype universitaire, pas une application de production** : il n'y a pas d'audit de sécurité, pas de réinitialisation de mot de passe, pas d'envoi d'e-mails, une base SQLite et pas de file de jobs externe. Voir « Limites du prototype ».

## Contenu du dépôt

| Partie | Dossier | Description |
|---|---|---|
| Bibliothèque | `src/stochastiq/` | calculs (Qiskit), sans aucune dépendance web ; version 0.1.0 |
| API | `api/` | FastAPI, SQLAlchemy, SQLite, Alembic ; voir [`api/README.md`](api/README.md) |
| Application web | `web/` | React, Vite, TypeScript ; voir [`web/README.md`](web/README.md) |
| Dashboard Streamlit | `dashboard/` | **outil local, hors application web** ; voir [`dashboard/README.md`](dashboard/README.md) |
| Données de démo | `scripts/seed_demo.py` | comptes, projet et runs fictifs |
| Documentation | `docs/` | [architecture](docs/ARCHITECTURE.md), [rôles](docs/ROLES.md), [API](docs/API.md), [métriques](docs/METRIQUES.md) |

## Lancement en local (PowerShell)

Prérequis : Python 3.10 ou plus récent, Node.js 20 ou plus récent. Depuis la racine du dépôt :

```powershell
# 1. Environnement Python : bibliothèque et API
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,dashboard,examples]"
pip install -e ".\api[dev]"
Copy-Item .env.example api\.env          # adapter SECRET_KEY hors développement

# 2. API (http://localhost:8000, documentation sur /docs)
cd api
uvicorn stochastiq_api.main:app --reload --port 8000
```

Dans un second terminal :

```powershell
# 3. Application web (http://localhost:5173)
cd web
npm install
npm run dev
```

Données de démonstration (facultatif, depuis la racine, avec le venv actif) :

```powershell
python scripts\seed_demo.py --database-url sqlite:///./api/stochastiq.db
```

## Lancement avec Docker

```powershell
Copy-Item .env.example .env              # ENV=prod impose un SECRET_KEY d'au moins 32 caractères
docker compose up --build
```

L'application web est servie sur http://localhost:5173 et l'API sur http://localhost:8000. La base SQLite est conservée dans le volume `api-data`. Pour charger les données de démonstration dans le conteneur :

```powershell
docker compose exec api python /app/scripts/seed_demo.py
```

## Comptes de démonstration

`scripts/seed_demo.py` crée le projet « Démo universitaire », 4 runs réels de petite taille, des commentaires, deux circuits épinglés et une machine sans clé. Il crée aussi 4 comptes fictifs, tous avec le mot de passe `demo-stochastiq-2026` (affiché dans la sortie du script) :

| Compte | E-mail | Rôle | Titre |
|---|---|---|---|
| [Membre 1] | membre1@example.test | Propriétaire | CEO |
| [Membre 2] | membre2@example.test | Gestionnaire des machines | CTO |
| [Membre 3] | membre3@example.test | Éditeur | Chercheur |
| [Membre 4] | membre4@example.test | Lecteur | Stagiaire |

## Tests

```powershell
pytest                       # bibliothèque (depuis la racine)
cd api; pytest; cd ..        # API
cd web; npm test; npm run build
npx playwright install chromium; npx playwright test   # bout en bout, depuis web/
```

Le test de bout en bout démarre lui-même une API (avec une base temporaire) et le front. Il enchaîne : inscription, création d'un projet, diagnostic jusqu'au résultat, invitation d'un lecteur, qui voit le run mais ne peut pas en lancer.

## Bibliothèque : démarrage rapide

```python
from stochastiq import build_ansatz, expressibility, gradient_variance_details

qc = build_ansatz("hardware_efficient", n_qubits=4, layers=3)
print(expressibility(qc, n_samples=1000, seed=0))  # plus bas = plus expressif
print(gradient_variance_details(qc, seed=0)["active_mean_variance"])
```

Autres fonctions :
- `compare` : plusieurs ansatz et plusieurs graines ;
- `gradient_scaling` et `fit_decay` : plateau stérile ;
- `hardware_cost` : coût de transpilation ;
- `ansatz_structure` : dessin d'un circuit.

Le notebook [`examples/demo.ipynb`](examples/demo.ipynb) enchaîne ces appels.

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

## Limites du prototype

- **Invitations** : par lien seulement, **sans e-mail**. Le propriétaire transmet lui-même le lien.
- **Machines** : **aucune clé de machine réelle** n'est stockée, et aucun calcul n'est envoyé à une vraie machine. Une entrée « fournisseur + libellé » est purement déclarative.
- **Données** : base **SQLite**, adaptée à un usage local ou de démonstration.
- **Calculs** : **pas de file de jobs externe**. 2 calculs au plus en même temps, 10 minutes au plus chacun, et un redémarrage de l'API interrompt les calculs en cours.
- **Comptes** : **pas de réinitialisation de mot de passe**, pas de vérification de l'adresse e-mail.
- **Sécurité** : **pas d'audit de sécurité**. Le jeton est conservé dans `sessionStorage`, avec le compromis documenté dans `web/README.md`.
- **Métriques** :
  - l'expressibilité est surestimée avec peu d'échantillons : ne comparez qu'à nombre d'échantillons égal ;
  - les conclusions sur le plateau stérile dépendent de l'observable (locale Z0 ou globale Z⊗n) et du nombre de couches, alors que le coût réel d'un QCBM est plutôt global ;
  - la simulation est exacte et sans bruit ;
  - la transpilation est heuristique et dépend de la graine ;
  - aucun lien n'est démontré entre ces métriques et la qualité d'apprentissage.
- **Ansatz** : les 7 ansatz sont reconstruits d'après le rapport du projet. Ils sont vérifiés contre PennyLane si l'option `verify` est installée, mais pas contre le code d'origine de QCBM Lab.

## Hors périmètre

- Entraînement de QCBM.
- Connexion à de vraies machines (IBM, Origin).
- Envoi d'e-mails.
- Paiement.
- Mode multi-organisations.

## Feuille de route

Pistes envisagées après ce prototype, sans engagement :
- file de jobs externe et reprise des calculs après un redémarrage ;
- base PostgreSQL ;
- réinitialisation de mot de passe et envoi des invitations par e-mail ;
- cookie `HttpOnly` avec protection CSRF à la place de `sessionStorage` ;
- audit de sécurité ;
- comparaison avec le code d'origine des ansatz de QCBM Lab ;
- modèles de bruit dans les simulations.

## Citer ce travail

StochastiQ, prototype version 0.2.0 (bibliothèque `stochastiq` 0.1.0), dépôt StochastiQ_Lib : https://github.com/Ldvccc/StochastiQ_Lib.

## Licence

MIT, voir [`LICENSE`](LICENSE). Les évolutions sont listées dans [`CHANGELOG.md`](CHANGELOG.md).
