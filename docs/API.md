# API StochastiQ

La documentation interactive (OpenAPI) est servie par l'API elle-même sur http://localhost:8000/docs, et le schéma sur `/openapi.json`. Toutes les routes, sauf mention contraire, demandent l'en-tête `Authorization: Bearer <jeton>`. Le rôle minimal est indiqué pour les routes d'un projet ; un non-membre reçoit 404.

Les nombres sont renvoyés en JSON standard (point décimal ; `null` pour une valeur non définie). Les messages d'erreur sont en français (`{"detail": "..."}`).

## Comptes

| Méthode | Route | Description |
|---|---|---|
| POST | `/auth/register` | création de compte (public) ; mot de passe d'au moins 10 caractères |
| POST | `/auth/login` | JWT valable 12 h (public) |
| GET | `/me` | utilisateur connecté |

## Projets et membres

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| GET | `/projects` | connecté | projets dont l'utilisateur est membre, avec son rôle |
| POST | `/projects` | connecté | création ; le créateur devient propriétaire |
| GET | `/projects/{id}` | viewer | détail |
| PATCH | `/projects/{id}` | owner | nom, description, `share_results` (partage des résultats avec l'IA, faux par défaut) |
| DELETE | `/projects/{id}` | owner | suppression (en cascade) |
| GET | `/projects/{id}/members` | viewer | membres, rôles et titres |
| PATCH | `/projects/{id}/members/{user_id}` | owner | rôle et/ou titre |
| DELETE | `/projects/{id}/members/{user_id}` | owner | retrait (le dernier propriétaire est protégé) |

## Invitations (aucun e-mail envoyé)

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| POST | `/projects/{id}/invitations` | owner | crée une invitation de 7 jours et retourne son lien |
| GET | `/projects/{id}/invitations` | owner | invitations en attente |
| DELETE | `/projects/{id}/invitations/{invitation_id}` | owner | révocation |
| GET | `/invitations/{token}` | public | informations de l'invitation |
| POST | `/invitations/{token}/accept` | connecté | acceptation (même e-mail que l'invitation) |

## Runs, commentaires, activité

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| POST | `/projects/{id}/runs` | editor | `{"kind", "params"}` ; répond 202 avec le run `pending` |
| GET | `/projects/{id}/runs?status=&kind=&limit=&offset=` | viewer | liste paginée (sans les résultats) |
| GET | `/projects/{id}/runs/{run_id}` | viewer | détail avec le résultat |
| POST, GET | `/projects/{id}/runs/{run_id}/comments` | viewer | commentaires |
| GET | `/projects/{id}/activity?limit=&offset=` | viewer | fil d'activité, du plus récent au plus ancien |

Types de runs (`kind`) : `diagnostic`, `compare`, `scaling`, `hardware`, `training`, `noise` et `recommendation` ; paramètres dans [`api/README.md`](../api/README.md#runs). Limites : qubits de 2 à 8, couches de 1 à 8, échantillons de 50 à 5000, graines de 1 à 10, 2 runs en cours par utilisateur (429), 10 minutes au plus.

Un ansatz s'écrit soit par son nom du catalogue, soit `{"custom_id": n}` pour un ansatz personnalisé du projet. L'API remplace cet identifiant par le contenu complet de l'ansatz avant d'enregistrer le run, qui reste ainsi reproductible. Un run d'entraînement ou de recommandation recopie de même la distribution cible du problème.

## Problèmes (distributions cibles)

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| GET | `/distributions` | public | distributions de référence, tailles possibles, présence d'une graine |
| GET | `/projects/{id}/problems` | viewer | problèmes du projet (sans le vecteur de probabilités) |
| POST | `/projects/{id}/problems` | editor | problème depuis une distribution de référence `{name, reference: {distribution, n_qubits, seed}}` |
| POST | `/projects/{id}/problems/csv` | editor | import CSV `{name, format: "probabilities" \| "samples", content, ...}` : 1 Mo et 100 000 lignes au plus ; le texte n'est pas conservé |
| GET, PATCH, DELETE | `/projects/{id}/problems/{problem_id}` | viewer, editor, editor | détail (probabilités et caractéristiques), renommage, suppression |

## Ansatz personnalisés

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| GET | `/projects/{id}/custom-ansatz` | viewer | ansatz du projet |
| POST | `/projects/{id}/custom-ansatz` | editor | `{name, format: "spec", spec}` ou `{name, format: "qasm", qasm}` (OpenQASM 3, 20 000 caractères au plus) ; aucun code Python n'est accepté |
| GET, PATCH, DELETE | `/projects/{id}/custom-ansatz/{ansatz_id}` | viewer, editor, editor | détail, renommage, suppression |
| GET | `/projects/{id}/custom-ansatz/{ansatz_id}/structure?n_qubits=&layers=` | viewer | circuit en colonnes de portes et statistiques |

## Prédiction

| Méthode | Route | Rôle | Description |
|---|---|---|---|
| POST | `/projects/{id}/predict` | editor | `{problem_id, ansatz, layers, noise_profile, topology}` : TVD finale prédite, dégradation et TVD sous bruit si un profil est donné, avec l'intervalle 10-90 % ou le motif de son absence, les références et la validation qui correspond au cas ; 409 « Aucun modèle entraîné » sans modèle |

Méthode, validations et limites : [`PREDICTION.md`](PREDICTION.md). Le modèle est lu dans `MODELS_DIR` ; l'API l'entraîne au premier démarrage du conteneur s'il est absent.

## Circuits épinglés et machines

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/projects/{id}/pins` | viewer |
| POST | `/projects/{id}/pins` | editor |
| DELETE | `/projects/{id}/pins/{pin_id}` | editor |
| GET, POST | `/projects/{id}/machines` | key_manager |
| DELETE | `/projects/{id}/machines/{machine_id}` | key_manager |

## Catalogue et métadonnées (publics)

| Méthode | Route | Description |
|---|---|---|
| GET | `/ansatz` | les 7 ansatz : nom technique, nom d'affichage, description, nombre de paramètres |
| GET | `/ansatz/{name}/structure?n_qubits=&layers=` | circuit en colonnes de portes et statistiques (`stats`) |
| GET | `/topologies` | topologies matérielles et libellés |
| GET | `/roles` | rôles et matrice de droits |
| GET | `/health` | disponibilité (healthcheck Docker) |
