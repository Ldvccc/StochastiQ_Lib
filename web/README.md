# Application web StochastiQ

Front React (Vite, TypeScript, React Router, Recharts) du prototype universitaire StochastiQ. Il ne fait qu'appeler l'API (`api/`). Les nombres reçus de l'API sont formatés à l'affichage en notation française (virgule décimale).

## Lancement (PowerShell)

L'API doit tourner sur http://localhost:8000 (voir `api/README.md`).

```powershell
cd web
npm install
Copy-Item .env.example .env   # VITE_API_URL, si l'API n'est pas sur le port 8000
npm run dev                   # http://localhost:5173
```

Autres commandes : `npm test` (Vitest et React Testing Library), `npm run build` (vérification des types, puis build dans `dist/`).

## Session

Le jeton JWT est gardé en mémoire et dans `sessionStorage`. C'est un compromis :
- la session survit au rechargement de l'onglet et disparaît à sa fermeture ;
- en revanche, un script injecté (XSS) pourrait lire le jeton.

Un cookie `HttpOnly` serait plus sûr, mais il demanderait une protection CSRF, hors périmètre de ce prototype. Toute réponse 401 de l'API efface la session et renvoie vers la page de connexion.

## Rôles dans l'interface

La matrice des droits vient de l'API (`GET /roles`). Une action interdite par le rôle reste visible : elle est désactivée, avec la raison en infobulle et pour les lecteurs d'écran.

## Charte

Les couleurs, polices, rayons, ombres et l'anneau de focus de la charte StochastiQ sont définis en variables CSS dans `src/styles/theme.css`, sans framework CSS. Les contrastes texte/fond respectent 4,5:1. Pour cette raison, le texte corail n'est jamais posé sur le fond violet clair (4,19:1).
