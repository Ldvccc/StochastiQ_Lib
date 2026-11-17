# API StochastiQ

API FastAPI du prototype universitaire StochastiQ : comptes, projets, rôles et invitations. Elle importe la bibliothèque `stochastiq` ; la bibliothèque, elle, ne dépend pas de l'API.

Ce n'est pas une application de production : il n'y a ni audit de sécurité, ni réinitialisation de mot de passe, ni envoi d'e-mails.

## Installation et lancement (PowerShell)

Depuis la racine du dépôt :

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
pip install -e ".\api[dev]"
Copy-Item .env.example api\.env   # puis adapter SECRET_KEY
cd api
uvicorn stochastiq_api.main:app --reload --port 8000
```

La documentation interactive est servie sur http://localhost:8000/docs. Au démarrage, l'API applique elle-même les migrations Alembic. Pour les appliquer à la main : `alembic upgrade head`, depuis `api/`.

Tests :

```powershell
cd api
pytest
```

## Configuration

Variables d'environnement, ou fichier `.env` dans le dossier de lancement (voir `.env.example`) :

| Variable | Rôle | Défaut |
|---|---|---|
| `ENV` | `dev` autorise le secret par défaut ; toute autre valeur l'interdit | `dev` |
| `SECRET_KEY` | secret de signature des JWT (32 caractères au moins hors `dev`) | valeur de développement |
| `DATABASE_URL` | base SQLAlchemy | `sqlite:///./stochastiq.db` |
| `CORS_ORIGIN` | seule origine autorisée (le front) ; sert aussi à construire les liens d'invitation | `http://localhost:5173` |
| `RUN_TIMEOUT_SECONDS` | durée maximale d'un run, en secondes | `600` |
| `MODELS_DIR` | dossier du modèle de prédiction (`/data/models` sous Docker) ; voir `docs/PREDICTION.md` | `./models` |

## Sécurité de base

- **Mots de passe** : 10 caractères au moins, hachés avec argon2id.
- **Jetons** : JWT signés en HS256, valables 12 heures, transmis par l'en-tête `Authorization: Bearer`.
- **Entrées** : toutes validées par pydantic, avec refus des champs inconnus.
- **CORS** : limité à `CORS_ORIGIN`.
- **Journaux** : ni mot de passe ni jeton ; les jetons d'invitation présents dans les URL sont masqués dans les journaux d'accès.
- **Projets** : un utilisateur ne voit que les projets dont il est membre (404 sinon).

## Invitations

`POST /projects/{id}/invitations` retourne un **lien** d'invitation valable 7 jours. **Aucun e-mail n'est envoyé** : le propriétaire transmet le lien lui-même. Pour accepter, la personne invitée se connecte avec l'adresse invitée, puis appelle `POST /invitations/{token}/accept`.

## Rôles

Les rôles sont ordonnés : `viewer` < `editor` < `key_manager` < `owner`. La matrice des droits est servie par `GET /roles`. Le titre d'un membre (CEO, CTO...) est une simple étiquette, sans effet sur les droits. Le dernier propriétaire d'un projet ne peut être ni rétrogradé ni retiré.

## Runs

`POST /projects/{id}/runs` (rôle `editor` au moins) enregistre un calcul et répond 202 avec le run en statut `pending`. Suivez ensuite son statut avec `GET /projects/{id}/runs/{run_id}` : `pending`, puis `running`, puis `done` ou `failed`. Types de calcul (`kind`) :

| `kind` | Paramètres principaux | Résultat |
|---|---|---|
| `diagnostic` | `ansatz`, `n_qubits`, `layers`, `n_samples`, `seed`, `observable` (`Z0`, `Zmean`, `Zall`) | expressibilité, intrication, variance du gradient (moyenne, active, part d'inactifs), statistiques, histogramme des fidélités |
| `compare` | liste `ansatz`, `n_qubits`, `layers`, `n_samples`, `n_seeds`, `seed` | lignes de `compare(...)` avec l'indicateur `pareto` |
| `scaling` | `ansatz` (1 à 4), `qubit_min`, `qubit_max`, `layers`, `layers_mode`, `n_samples`, `observable` ou `compare_observables`, `seed` | séries par ansatz et observable, ajustements `fit_decay` (actifs et tous) |
| `hardware` | `ansatz`, `n_qubits`, `layers`, `topology`, `seed` | `hardware_cost(...)` |
| `training` | `problem_id`, `ansatz`, `layers`, `loss` (`kl`, `mmd`, `tvd`), `optimizer` (`adam`, `spsa`, `cobyla`), `max_iter` (10 à 1000), `learning_rate`, `shots` (null ou 100 à 100 000), `seed`, `evaluate_noise` (`{profile, topology}`, facultatif) | `train_qcbm(...)` : paramètres, historique, distribution apprise, KL, TVD, Hellinger ; références classiques ; caractéristiques du problème ; `noise` (métriques sous bruit) |
| `noise` | `ansatz`, `n_qubits`, `layers`, `profile` (`faible`, `moyen`, `fort` ou `{p1, p2, readout}`), `topology` (`line`, `ring`, `full`), `n_samples` (1 à 200), `seed` | `noisy_tvd(...)` : TVD moyenne idéal / bruité sur des paramètres aléatoires |
| `recommendation` | `problem_id`, `ansatz` (2 à 7), `layers`, `noise_profile`, `topology`, `budget` (200 à 7000 itérations), `n_samples`, `seed` | par ansatz : diagnostic léger, prédiction, mesure si un entraînement existe ; références classiques ; classement et verdict (`justified`, `not_justified`, `undetermined`, ansatz à entraîner) |

Le run `diagnostic` accepte aussi `noise_profile` (facultatif) : la carte « Dégradation sous bruit » (20 jeux de paramètres, topologie en ligne). Le run `recommendation` demande un modèle de prédiction (409 sinon) ; les entraînements déjà réussis du projet, sur le même problème et le même nombre de couches, sont recopiés dans ses paramètres (`existing`) et priment sur la prédiction.

Chaque run réussi de diagnostic, de bruit ou d'entraînement ajoute des lignes à la base de résultats (table `results`) : caractéristiques du circuit et du problème, profil de bruit, grandeurs mesurées ; jamais les probabilités du client.

Limites validées par l'API : qubits de 2 à 8, couches de 1 à 8, échantillons de 50 à 5000, graines (`n_seeds`) de 1 à 10, 2 runs en cours au plus par utilisateur (429 au-delà), durée maximale de 10 minutes.

Exécution : au plus 2 calculs tournent en même temps. Chaque run s'exécute dans son propre `ProcessPoolExecutor` à un seul worker, pour qu'un run qui dépasse la durée maximale puisse être arrêté sans toucher aux autres. Au démarrage, l'API passe en `failed` les runs restés `pending` ou `running`, avec un message explicite. Il n'y a pas de file de jobs externe : un redémarrage de l'API interrompt les calculs en cours.

## Collaboration

- **Commentaires** : `POST/GET /projects/{id}/runs/{run_id}/comments`, ouverts aux lecteurs.
- **Fil d'activité** : `GET /projects/{id}/activity?limit=&offset=`. Il enregistre le lancement et la fin des runs, les commentaires, les circuits épinglés, les invitations, les adhésions, les changements de rôle et les machines ajoutées.
- **Circuits épinglés** : `GET/POST /projects/{id}/pins` et `DELETE /projects/{id}/pins/{pin_id}`, à partir du rôle `editor`.
- **Machines** : `GET/POST /projects/{id}/machines` et `DELETE /projects/{id}/machines/{machine_id}`, à partir du rôle `key_manager`. Une entrée ne contient qu'un fournisseur et un libellé. **Aucune clé n'est stockée** : un champ `secret`, `api_key`, `token`, `key` ou `password` est refusé (422). La vraie gestion des clés de machines est hors périmètre de ce prototype.

## Catalogue

`GET /ansatz`, `GET /ansatz/{name}/structure?n_qubits=&layers=` (circuit en colonnes de portes, pour le dessin) et `GET /topologies`. Ces routes sont publiques.
