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
| PATCH | `/projects/{id}` | owner | nom, description |
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

Types de runs (`kind`) et paramètres : voir [`api/README.md`](../api/README.md#runs). Limites : qubits de 2 à 8, couches de 1 à 8, échantillons de 50 à 5000, graines de 1 à 10, 2 runs en cours par utilisateur (429), 10 minutes au plus.

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
