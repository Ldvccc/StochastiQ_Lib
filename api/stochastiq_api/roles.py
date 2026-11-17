"""Rôles d'un membre de projet et matrice de droits.

Les rôles sont ordonnés : chaque rôle a tous les droits des rôles
inférieurs. Le titre d'un membre (CEO, CTO...) est une étiquette libre, sans
effet sur les droits.
"""

from typing import Literal

Role = Literal["viewer", "editor", "key_manager", "owner"]

ROLES: tuple[str, ...] = ("viewer", "editor", "key_manager", "owner")

ROLE_LABELS = {
    "viewer": "Lecteur",
    "editor": "Éditeur",
    "key_manager": "Gestionnaire des machines",
    "owner": "Propriétaire",
}

_RANK = {role: rank for rank, role in enumerate(ROLES)}

# Action -> rôle minimal. Source unique de la matrice, servie au front par GET /roles.
PERMISSIONS: list[dict[str, str]] = [
    {"action": "read", "label": "Lire le projet, les runs, les rapports et les membres", "min_role": "viewer"},
    {"action": "comment", "label": "Commenter les runs", "min_role": "viewer"},
    {"action": "run", "label": "Lancer des runs", "min_role": "editor"},
    {"action": "pin", "label": "Épingler et désépingler des circuits", "min_role": "editor"},
    {"action": "problems", "label": "Créer, renommer et supprimer des problèmes", "min_role": "editor"},
    {"action": "custom_ansatz", "label": "Créer, renommer et supprimer des ansatz personnalisés", "min_role": "editor"},
    {
        "action": "machines",
        "label": "Gérer les machines (fournisseur et libellé, sans clé)",
        "min_role": "key_manager",
    },
    {
        "action": "edit_project",
        "label": "Modifier le nom et la description du projet, partager ses résultats avec l'IA",
        "min_role": "owner",
    },
    {"action": "invite", "label": "Inviter des membres et révoquer des invitations", "min_role": "owner"},
    {
        "action": "manage_members",
        "label": "Changer les rôles et les titres, retirer des membres",
        "min_role": "owner",
    },
    {"action": "delete_project", "label": "Supprimer le projet", "min_role": "owner"},
]

MIN_ROLE = {permission["action"]: permission["min_role"] for permission in PERMISSIONS}


def has_role(role: str, min_role: str) -> bool:
    """True si ``role`` vaut au moins ``min_role`` dans l'ordre des rôles."""
    return _RANK[role] >= _RANK[min_role]
