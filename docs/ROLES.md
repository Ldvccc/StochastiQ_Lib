# Rôles et droits

Chaque membre d'un projet a un rôle. Les rôles sont ordonnés, et chacun inclut tous les droits des rôles précédents :

`viewer` (Lecteur) < `editor` (Éditeur) < `key_manager` (Gestionnaire des machines) < `owner` (Propriétaire)

| Action | Lecteur | Éditeur | Gestionnaire des machines | Propriétaire |
|---|---|---|---|---|
| Lire le projet, les runs, les rapports et les membres | Oui | Oui | Oui | Oui |
| Commenter les runs | Oui | Oui | Oui | Oui |
| Lancer des runs | Non | Oui | Oui | Oui |
| Épingler et désépingler des circuits | Non | Oui | Oui | Oui |
| Créer, renommer et supprimer des problèmes | Non | Oui | Oui | Oui |
| Créer, renommer et supprimer des ansatz personnalisés | Non | Oui | Oui | Oui |
| Gérer les machines (lister, ajouter, retirer des entrées fournisseur + libellé, sans clé) | Non | Non | Oui | Oui |
| Modifier le nom et la description du projet, partager ses résultats avec l'IA | Non | Non | Non | Oui |
| Inviter des membres, voir et révoquer les invitations | Non | Non | Non | Oui |
| Changer les rôles et les titres, retirer des membres | Non | Non | Non | Oui |
| Supprimer le projet | Non | Non | Non | Oui |

La source unique de cette matrice est `api/stochastiq_api/roles.py`. Elle est servie par `GET /roles` et affichée dans la page Équipe de l'application web.

## Règles complémentaires

- **Non-membres** : un utilisateur qui n'est pas membre d'un projet reçoit 404 pour toute route de ce projet, ce qui ne révèle pas son existence. Un membre au rôle insuffisant reçoit 403, avec le rôle minimal requis.
- **Dernier propriétaire** : il ne peut être ni rétrogradé ni retiré (409).
- **Titre** : le « titre dans la startup » (CEO, CTO...) est une étiquette libre, sans aucun effet sur les droits.
- **Machines** : une entrée ne contient qu'un fournisseur et un libellé. L'API refuse tout champ `secret`, `api_key`, `token`, `key` ou `password` (422). La vraie gestion des clés de machines est hors périmètre de ce prototype.
- **Partage des résultats** : désactivé par défaut. Activé par le propriétaire, il ajoute aux données d'entraînement de l'IA de prédiction les caractéristiques et les grandeurs mesurées des runs réussis du projet, jamais les distributions de ses problèmes.
- **Prédiction et recommandation** : `POST /predict` et le run `recommendation` demandent le droit de lancer des runs (éditeur).
- **Invitations** : un lien valable 7 jours. Aucun e-mail n'est envoyé. Pour accepter, l'utilisateur doit être connecté avec l'adresse invitée.
- **Interface** : une action interdite par le rôle reste visible. Elle est désactivée, avec la raison en infobulle et pour les lecteurs d'écran.

## Écart par rapport à la consigne

La consigne place « liste des machines » dans les droits du gestionnaire des machines. L'API applique cette règle : lire la liste demande donc le rôle `key_manager`. L'écran Matériel indique aux autres rôles que la liste leur est réservée, et affiche le simulateur local, qui reste toujours disponible.
