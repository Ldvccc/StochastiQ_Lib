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
