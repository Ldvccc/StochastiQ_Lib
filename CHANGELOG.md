# Historique des versions

## Non publié

### Corrigé
- Recommandation : un ansatz déjà entraîné dans le projet, dont seule la dégradation sous bruit est prédite, pouvait encore être proposé à l'entraînement ; il ne l'est plus.
- Recommandation et rapport : quand le budget ne permet pas d'entraîner tous les ansatz encore ouverts, la phrase le dit (nombre d'ansatz ouverts, nombre d'entraînements permis, ansatz restant à départager).
- Rapport : le diagnostic léger (200 échantillons) est signalé comme indicatif et sans effet sur la prédiction.

## 0.3.0 (2026-11-08)

Un client apporte sa distribution et ses ansatz, les entraîne en simulation, avec ou sans bruit, les compare à des méthodes classiques simples, et obtient une prédiction et une recommandation. API et application web en version 0.3.0, bibliothèque `stochastiq` en version 0.2.0 (toujours sans dépendance web).

### Dérogations validées par l'auteur
- **Périmètre** : l'entraînement de QCBM en simulation et le bruit simulé (qiskit-aer) entrent dans le périmètre.
- **Dashboard Streamlit** : il n'est pas étendu. Les phrases de lecture des nouvelles fonctions (entraînement, bruit, recommandation) n'existent que dans l'application web.
- **Verdict de la recommandation** (jalon 8) : une valeur mesurée n'est plus traitée comme un intervalle de largeur nulle. Règle des 10 % pour une valeur mesurée (sinon « Équivalent au classique (écart inférieur à 10 %) »), règle des bornes pour une prédiction avec intervalle, marge de 2 × l'erreur moyenne de validation pour une prédiction sans intervalle (verdicts « probablement »). Même règle des 10 % pour la phrase de l'écran Entraînement. Détails : `docs/PREDICTION.md`.
- **Critère de l'IA de prédiction** (jalon 6) : le critère initial, qui mélangeait précision et intervalles, est séparé en deux. La valeur centrale du modèle est retenue si son gain sur la meilleure référence atteint 20 % ; l'intervalle est calibré par CQR et n'est affiché que si sa couverture mesurée, pour un cas comparable, est entre 70 % et 90 %. Résultats avant et après : `docs/PREDICTION.md`.

### Bibliothèque (`stochastiq` 0.2.0)
- `distributions` : six distributions de référence (gaussienne, bimodale, log-normale, uniforme, Bars-and-Stripes, Boltzmann d'Ising), imports d'échantillons et de probabilités, caractéristiques d'un problème.
- `custom_ansatz` : ansatz par spec JSON (rotations, motif d'intrication, CNOT choisis) ou par texte OpenQASM 3 (option `qasm3`), validation des portes et des tailles, structure pour le dessin.
- `training` : entraînement QCBM (pertes KL, MMD et TVD ; optimiseurs Adam, SPSA et COBYLA ; probabilités exactes ou par tirages ; graine), métriques KL, TVD et Hellinger.
- `baselines` : marginales indépendantes et arbre de Chow-Liu.
- `noise` (option `noise`, qiskit-aer) : profils faible, moyen et fort ou personnalisé, probabilités bruitées sur le circuit transpilé (ligne, anneau, complète), TVD moyenne idéal / bruité, comptes de portes et fidélité par comptage.
- `circuit_features` ; `gradient_scaling` accepte un constructeur de circuit ; probabilités en lot exposées sans changer les résultats existants.
- Qiskit 1.3 au minimum.

### API (0.3.0)
- Problèmes : distributions de référence ou import CSV (1 Mo et 100 000 lignes au plus, texte non conservé), droit `problems` (éditeur), événement `problem_added`.
- Ansatz personnalisés (spec ou OpenQASM 3, jamais de code Python), droit `custom_ansatz` (éditeur) ; les runs acceptent `{"custom_id": n}`, résolu en contenu complet pour rester reproductibles.
- Runs `training` (avec évaluation facultative sous bruit), `noise` et `recommendation` ; carte « Dégradation sous bruit » dans le diagnostic.
- Base de résultats (`results`, migration 0005), alimentée par les runs réussis et par la grille de référence ; jamais de probabilités brutes. Partage des résultats d'un projet avec l'IA (`share_results`, faux par défaut, propriétaire).
- IA de prédiction (`api/stochastiq_api/ml/`, scikit-learn et joblib) : TVD finale et dégradation sous bruit, quatre validations, intervalle CQR ; `POST /projects/{id}/predict` (409 sans modèle).
- Recommandation : classement de 2 à 7 ansatz, entraînements existants prioritaires, références classiques, verdict selon la nature de la preuve (mesure, intervalle ou marge), ansatz à entraîner pour trancher.
- Processus de calcul créés par `spawn` sur toutes les plateformes (sous Linux, `fork` bloquait un routage Qiskit après une transpilation dans le processus de l'API).
- Message de durée maximale construit à partir de `RUN_TIMEOUT_SECONDS` ; réglage `MODELS_DIR`.

### Application web (0.3.0)
- Écrans Problèmes, Mes ansatz, Entraînement (courbe de perte en échelle logarithmique, distribution apprise, quantique contre classique, évaluation sous bruit), Recommandation et Rapport imprimable (CSV et JSON).
- Carte « Dégradation sous bruit » dans le Diagnostic ; ansatz personnalisés proposés dans les formulaires existants ; partage des résultats avec l'IA sur la page du projet.

### Données, scripts et déploiement
- `scripts/build_results.py` : grille de référence (7 ansatz × distributions × 2 à 6 qubits × 1 à 4 couches, entraînement exact puis 3 profils de bruit), reprise, `--measure`, `--limit`, `--export` ; export `data/results_grid.csv` (3024 lignes).
- `scripts/train_predictor.py` : validations et entraînement de l'IA ; option `--layers` pour un modèle réduit.
- Le conteneur de l'API et `scripts/seed_demo.py` entraînent le modèle de prédiction s'il est absent de `MODELS_DIR`.
- Démo enrichie : problème de référence, problème CSV, ansatz personnalisé, entraînement, recommandation.
- Playwright : nouveau parcours de recommandation ; les tests de bout en bout entraînent un modèle réduit dans un dossier temporaire.
- Documentation : `docs/PREDICTION.md`, et mise à jour du README, de `API.md`, `ROLES.md`, `METRIQUES.md`, `ARCHITECTURE.md` et des deux rapports.

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
