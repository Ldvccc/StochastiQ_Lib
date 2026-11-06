# Historique des versions

## 0.2.0 (2026-11-06)

Prototype web complet. La bibliothèque `stochastiq` reste en version 0.1.0, sans dépendance web.

### API (`api/`)
- FastAPI, SQLAlchemy 2, SQLite et Alembic (migrations appliquées au démarrage).
- Comptes : mots de passe d'au moins 10 caractères, hachés en argon2id ; JWT signés et valables 12 heures ; refus de démarrer avec le secret par défaut hors développement ; CORS limité au front ; jetons d'invitation masqués dans les journaux.
- Projets, membres et 4 rôles (lecteur, éditeur, gestionnaire des machines, propriétaire), avec une matrice de droits servie par `GET /roles`. Le dernier propriétaire est protégé, et les projets sont isolés (404 pour un non-membre).
- Invitations par lien valable 7 jours, sans envoi d'e-mail.
- Runs `diagnostic`, `compare`, `scaling` et `hardware` exécutés hors processus : 2 calculs au plus, 10 minutes au plus, bornes de calcul validées, 2 runs en cours au plus par utilisateur, runs orphelins repris au démarrage.
- Commentaires, fil d'activité, circuits épinglés, machines « fournisseur + libellé » sans aucune clé stockée.
- Catalogue des ansatz, structure de circuit et statistiques, topologies.

### Application web (`web/`)
- React, Vite, TypeScript, React Router, Recharts ; charte StochastiQ en variables CSS, contrastes d'au moins 4,5:1, cibles tactiles de 44 px, affichage correct jusqu'à 390 px de large.
- Écrans Connexion, Inscription, Projets, Projet (Activité, Circuits épinglés, Runs, Membres), Équipe (rôles, titres, invitations par lien, matrice des droits) et acceptation d'invitation.
- Écrans Diagnostic, Comparateur (front de Pareto), Ansatz (schéma SVG), Plateau stérile (échelle logarithmique, coûts local et global), Jobs et matériel (runs, coût de transpilation, machines) et détail d'un run.
- Règles de lecture copiées du dashboard Streamlit, export CSV, nombres en notation française.
- Actions interdites par le rôle désactivées avec une explication, jamais masquées.

### Déploiement et documentation
- `docker-compose.yml` (API avec healthcheck et volume SQLite, front servi par nginx), Dockerfiles, `.env.example`.
- `scripts/seed_demo.py` : comptes, projet et runs de démonstration.
- `docs/ARCHITECTURE.md`, `docs/ROLES.md`, `docs/API.md` ; README mis à jour (lancement PowerShell et Docker, limites, feuille de route).
- Tests : API (pytest), front (Vitest et React Testing Library), bout en bout (Playwright).

## 0.1.0 (2026-11-06)

Première version du prototype.

### Ansatz
- Les 7 ansatz de QCBM Lab, reconstruits d'après le rapport du projet (section 2.4) : `basic_entangler`, `strongly_entangling`, `hardware_efficient`, `rotation_only`, `all_to_all`, `brick_wall`, `data_reuploading` (`build_ansatz`, `list_ansatz`).
- Description structurée d'un ansatz en colonnes de portes, pour le dessiner (`ansatz_structure`).
- Vérification contre PennyLane (option `verify`) : gabarits `BasicEntanglerLayers` et `StronglyEntanglingLayers`, et circuits de référence en portes PennyLane pour les autres.

### Métriques
- Expressibilité de Sim et al. (2019) et histogramme des fidélités comparé à la référence de Haar (`expressibility`, `fidelity_histogram`).
- Capacité d'intrication de Meyer-Wallach (`entangling_capability`).
- Variance du gradient par la règle du décalage de paramètre, calculée pour chaque paramètre, avec les observables `Z0` (coût local), `Zmean` et `Zall` (produit des Z, coût global). Sorties : moyenne sur tous les paramètres, moyenne sur les paramètres actifs, part des paramètres inactifs (`gradient_variance`, `gradient_variance_details`).
- Statistiques de circuit : profondeur, portes à 2 qubits, portes par type (`circuit_stats`).
- Comparaison de plusieurs ansatz en `pandas.DataFrame`, avec moyenne et écart-type sur plusieurs graines (`compare`). Front de Pareto (`pareto_front`).

### Coût matériel
- Transpilation hors ligne sur les topologies ligne, anneau, complète et heavy-hex (`hardware_cost`, `list_topologies`). Trois niveaux de mesure (circuit d'origine, traduction vers les portes de base, routage) et surcoût du routage isolé.

### Plateau stérile
- Variance du gradient en fonction du nombre de qubits, à profondeur fixe ou proportionnelle (`gradient_scaling`). Ajustement exponentiel avec facteur par qubit et R² (`fit_decay`).

### Dashboard
- Dashboard Streamlit local (`streamlit run dashboard/app.py`), en français, aux couleurs StochastiQ. Cinq onglets : Diagnostic, Comparateur (avec le nuage de Pareto), Ansatz, Matériel et Plateau stérile.
- Phrases de lecture générées à partir des chiffres, avec des seuils explicites. Avertissement sous 1000 échantillons, virgule décimale, export CSV des tableaux.

### Documentation
- `README.md`, `docs/METRIQUES.md` et le notebook `examples/demo.ipynb`.
