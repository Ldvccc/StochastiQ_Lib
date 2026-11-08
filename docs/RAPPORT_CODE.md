# Rapport 2 : le code de StochastiQ expliqué en détail (version 0.2.0)

Ce rapport explique **comment** le projet est construit : l'environnement, chaque fichier, les choix d'implémentation, les pièges déjà rencontrés et la façon d'étendre le code. Lisez d'abord le rapport 1 (`docs/RAPPORT_FONCTIONNALITES.md`), qui décrit ce que fait le projet et les conventions de l'auteur.

---

## 0. Environnement de travail (machine de l'auteur)

- **OS** : Windows 11, avec PowerShell et Git Bash. Dossier : `C:\Users\ldvcb\Desktop\Sto\StochastiQ_Lib`.
- **Python** : `.venv` (Python 3.12.10, pyenv-win) à la racine. Tout y est installé en mode éditable :
  - `pip install -e ".[dev,dashboard,examples,verify]"` ;
  - `pip install -e "./api[dev]"`.

  Versions notables : qiskit 2.6.x, numpy 2.5, pandas, PennyLane 0.45.1, streamlit 1.66, fastapi 0.162, SQLAlchemy 2.1, alembic 1.20, pydantic 2.14, PyJWT 2.15, argon2-cffi 25.1.

  Les Python 3.11 et 3.13 sont aussi présents (`py -0`), mais **pas la 3.10**.
- **Node** : Node 22.15 et npm 10.9. `web/node_modules` est installé, ainsi que Chromium pour Playwright (`npx playwright install chromium`).
- **Docker** : 29.4 avec Compose v5.1, démon actif. Les images `stochastiq_lib-api` et `stochastiq_lib-web` ont déjà été construites.
- **Pièges des outils, déjà rencontrés** :
  - **Heredoc** : dans l'outil Bash de l'agent, un heredoc contenant certaines apostrophes a provoqué « unexpected EOF ». Pour du code long, écrire un fichier avec l'outil d'écriture, ou un script Python dans le scratchpad, plutôt qu'un heredoc.
  - **`sed`** : il mange les séquences `\u202f`. Utiliser l'outil d'édition pour les remplacements délicats.
  - **Chemins Git Bash** : Git Bash convertit `/app/...` en chemin Windows dans les commandes `docker exec`. Préfixer par `MSYS_NO_PATHCONV=1`. PowerShell n'a pas ce problème.
  - **Console** : elle est en cp1252. Pour afficher les accents d'un script Python : `PYTHONIOENCODING=utf-8`.
  - **Processus** : sous Windows, `ProcessPoolExecutor` utilise *spawn*. Les fonctions envoyées au worker doivent donc être importables au niveau d'un module (c'est le cas de `stochastiq_api.runner.execute`).
  - **Arrêter un serveur** sur un port : `powershell -Command "Get-NetTCPConnection -LocalPort 8000 -State Listen | % { Stop-Process -Id $_.OwningProcess -Force }"`.

---

## 1. Arborescence

```
pyproject.toml            bibliothèque (setuptools, src/) ; extras dev, dashboard, examples, verify ; pytest testpaths=["tests"]
src/stochastiq/           bibliothèque (8 fichiers)
tests/                    tests de la bibliothèque + test_dashboard.py (Streamlit) + test_ansatz_pennylane.py
dashboard/                app.py (Streamlit), ui.py (fonctions pures + graphiques), README.md
.streamlit/config.toml    thème Streamlit
examples/demo.ipynb       notebook de démonstration
api/                      pyproject.toml, alembic.ini, Dockerfile, README.md, stochastiq_api/, tests/
web/                      package.json, vite.config.ts, tsconfig.json, index.html, Dockerfile, nginx.conf,
                          playwright.config.ts, e2e/, src/
scripts/seed_demo.py      données de démonstration
docs/                     METRIQUES, ARCHITECTURE, ROLES, API, ces deux rapports
docker-compose.yml, .dockerignore, .env.example, .gitignore, .github/workflows/tests.yml, CHANGELOG.md, LICENSE
```

---

## 2. Bibliothèque `src/stochastiq/`

`__init__.py` réexporte les fonctions publiques (`__all__`) et fixe `__version__ = "0.1.0"`. Aucun module n'importe quoi de web.

### 2.1 `ansatz.py`

- **Docstring du module** : définition des 7 ansatz « d'après le rapport QCBM Lab, section 2.4 », cas n=1 et n=2 compris. Toute modification d'un ansatz doit la tenir à jour.
- **Entangleurs** : une fonction `(n_qubits, layer) -> list[(contrôle, cible)]` par motif. `_ring` (vide si n<2), `_basic_ring` (n=2 donne [(0,1)], sinon `_ring`), `_strongly_ranges` (r = layer % (n−1) + 1), `_linear`, `_none`, `_all_pairs`, `_brick` (`range(layer % 2, n−1, 2)`).
- **`_ANSATZ`** : dictionnaire nom → (tuple des rotations, fonction d'entangleurs). Pour ajouter un ansatz, il suffit d'une entrée ici, puis de mettre à jour la docstring, `api/stochastiq_api/catalog.py` (`ANSATZ_INFO`), les libellés d'affichage (`dashboard/ui.py ANSATZ_LABELS`, `web/src/lib/reading.ts ANSATZ_LABELS`) et les tests (`tests/test_ansatz.py EXPECTED`, `tests/test_ansatz_pennylane.py`).
- **`build_ansatz`** : `ParameterVector("θ", layers*n*k)`. Boucle couche → qubit → rotation, avec `getattr(qc, rotation)(theta[(layer*n+j)*k + r], j)`, puis les CNOT. Lève `ValueError` en listant les noms valides.
- **`ansatz_structure`** : mêmes boucles, mais produit des colonnes. Pour chaque couche : une colonne par indice de rotation r (contenant les n qubits), puis une colonne par CNOT. Le type vaut `rotation.upper()`. Ses comptes sont testés égaux à `circuit_stats(...)["gate_counts"]`.

### 2.2 `metrics.py`

- **`fidelity_histogram`** :
  - tire `n_samples` paires θ1, θ2 ∈ U[0, 2π]^P avec `default_rng(seed)` (ordre : θ1 puis θ2, à chaque échantillon) ;
  - construit `Statevector(ansatz.assign_parameters(θ))` et calcule F = |vdot|² ;
  - calcule l'histogramme sur `linspace(0,1,n_bins+1)` et les probabilités de Haar `diff(1-(1-edges)**(d-1))` ;
  - lève `ValueError` sans paramètre.
- **`expressibility`** : appelle `fidelity_histogram`, puis `sum(p * log((p+ε)/(q+ε)))` avec ε=1e-12. Le refactoring a été validé à valeur identique par `tests/test_fidelity_histogram.py`, qui contient des valeurs de référence figées (0.4108859559616048 et 0.08902782302132872).
- **`_meyer_wallach(state, n)`** : remet l'état en forme `[2]*n` ; pour chaque k, `moveaxis(k → 0)`, `reshape(2,-1)`, ρ = M·M†, pureté Tr(ρ²) ; renvoie Q = 2(1 − moyenne des puretés). L'ordre des axes est sans importance, puisqu'on moyenne sur tous les qubits.
- **`entangling_capability`** : moyenne de Q sur des états aléatoires.

### 2.3 `stats.py`

- `circuit_stats` : `transpile(ansatz, basis_gates=["ry","rz","rx","cx","h"], optimization_level=0)`.
- `gate_counts` est tiré de `count_ops()`, sans `barrier`.
- `n_two_qubit_gates` compte les instructions à 2 qubits, hors barrières.
- `depth()` vient de Qiskit, qui parallélise les portes : c'est pourquoi la profondeur ne se déduit pas des colonnes de `ansatz_structure`, et que l'API renvoie `stats` à côté de la structure.

### 2.4 `gradients.py` (le module le plus délicat)

**Pourquoi un simulateur numpy en lot ?** Avec `Statevector`, une évaluation coûte environ 5 ms. La règle du décalage demande 2·P évaluations par point, soit 72 pour P=36. Un `compare` complet aurait pris environ 1 h 30. Toutes les évaluations décalées sont donc simulées **en lot** avec numpy.

- **Disposition des états** : le tableau a la forme `(B, 2, …, 2)`, et le qubit q est sur l'**axe `n - q`** (convention little-endian de Qiskit : l'axe 1 porte le qubit de poids fort).
- **Fonctions internes** :
  - `_rotation_matrices(name, angles)` donne des matrices `(B,2,2)` pour RX, RY ou RZ ;
  - `_apply_batched_1q` fait un `einsum("b...j,bij->b...i")` après `moveaxis` ;
  - `_apply_fixed(states, matrix, axes)` applique une porte fixe à k qubits par `tensordot`. La matrice de l'opérateur Qiskit est remise en forme `(2,)*2k`, et les axes sont passés dans l'ordre `[n - q for q in reversed(qubits)]`.
- **`_expectations(ansatz, thetas, z_qubits, product=False)`** :
  - parcourt `ansatz.data` en ignorant les barrières ;
  - une porte paramétrée doit être rx, ry ou rz, avec un angle qui est exactement un objet `Parameter`. Sinon : `ValueError` « Porte … non supportée » ;
  - les portes fixes passent par `Operator(op).data` ;
  - à la fin, on prend les probabilités |ψ|². Si `product` est vrai, on multiplie par le signe ±1 sur chaque axe des qubits mesurés, puis on somme (valeur de Z⊗…⊗Z). Sinon, on calcule la marginale de chaque qubit (p0 − p1) et on prend la moyenne.
- **`_cost_terms(observable, n)`** : `"Z0"` → ([0], False), `"Zmean"` → (tous, False), `"Zall"` → (tous, True), sinon `ValueError` qui liste les trois noms.
- **`gradient_variance_details`** :
  - `thetas = rng.uniform(0, 2π, (n_samples, P))`. Le tirage en un seul bloc donne la même suite que les anciens tirages ligne par ligne ;
  - matrice des décalages `(2P, P)` : la ligne 2p vaut +π/2 sur p, la ligne 2p+1 vaut −π/2 ;
  - lots de taille `chunk = max(1, 2**21 // (2P · 2^n))` échantillons, ce qui borne la mémoire à environ 2 millions d'amplitudes ;
  - gradient = (coûts pairs − coûts impairs)/2 ; `variances = gradients.var(axis=0)` (ddof=0) ;
  - `active = variances >= 1e-12` ; `active_mean_variance` vaut `nan` si aucun paramètre n'est actif.
  - Les tests vérifient l'égalité avec un calcul `Statevector` explicite, à 1e-12 près, pour Z0, Zmean et Zall (avec `SparsePauliOp("Z"*n)` pour ce dernier).
- **`gradient_variance`** renvoie `details["mean_variance"]`.

### 2.5 `compare.py`

- `_METRICS` contient expressibility et entangling_capability.
- `_aggregate(row, metric, values)` met la valeur seule s'il n'y a qu'une graine, sinon la moyenne et `<metric>_std` (`np.std(ddof=1)`).
- Les graines valent `[seed+i …]`, ou `[None]*n` si `seed` est None.
- Le gradient passe par **un seul appel** à `gradient_variance_details` par graine, qui sert à gradient_variance, gradient_variance_active et inactive_fraction.
- `pareto_front` se ramène à deux critères à minimiser (signes inversés selon les options), puis applique un test de dominance en O(n²).

### 2.6 `scaling.py`

- `gradient_scaling` valide `layers_mode` dans `("fixed","linear")` et refuse une plage vide (`ValueError`).
- Pour chaque n, avec couches = `layers` ou `n` selon le mode : `build_ansatz`, puis `gradient_variance_details`, puis une ligne du tableau. `callback(done, total)` est appelé après chaque n.
- `fit_decay` filtre les valeurs v > 0 (ce qui élimine aussi les `nan`), puis `np.polyfit(n, log v, 1)` ; R² = 1 − SSres/SStot, et 1.0 si SStot vaut 0.

### 2.7 `hardware.py`

- `_TOPOLOGIES` : `from_line`, `from_ring`, `from_full` (taille = nombre de qubits de l'ansatz) et `from_heavy_hex(distance=3)` (19 qubits).
- `hardware_cost` :
  - vérifie le nom et la taille ;
  - `before` provient de `circuit_stats` ;
  - `_transpiled(coupling_map)` appelle `transpile(..., basis_gates=["cx","rz","sx","x"], optimization_level=1, seed_transpiler=seed)` ;
  - `basis_only` utilise `CouplingMap.from_full(n)` ;
  - les clés à plat sont conservées pour la compatibilité.

---

## 3. Tests de la bibliothèque (`tests/`, 239 tests)

| Fichier | Contenu |
|---|---|
| test_ansatz.py | comptes de paramètres et de CNOT par ansatz (n=4, L=3 : dict `EXPECTED`), cas n=1 et n=2, ordre des paramètres, portées des CNOT, alternance de brick_wall, `ValueError` |
| test_ansatz_structure.py | comptes de `ansatz_structure` = `circuit_stats`, indices de paramètres complets, ordre des colonnes |
| test_ansatz_pennylane.py | `pytest.importorskip("pennylane")` ; 7 ansatz × n ∈ {2,3,4} × L ∈ {1,2,3} ; probabilités Qiskit remises en big-endian par `reshape([2]*n).transpose().ravel()` |
| test_expressibility.py, test_fidelity_histogram.py | plus de couches donne moins de divergence, reproductibilité, valeurs figées d'avant le refactoring |
| test_entangling_capability.py | Meyer-Wallach (état produit 0, Bell 1, GHZ 1), etc. |
| test_gradients.py | concordance avec Statevector, Zall avec SparsePauliOp, paramètres inactifs, moyenne active (ratio 1/(1−f)), tendance stable sur 3 graines (hardware_efficient, 10 couches, n=2,3,4) |
| test_compare.py, test_scaling.py, test_hardware.py, test_stats.py | colonnes, tri, `_std`, Pareto, fit_decay, coût global < coût local pour hardware_efficient, `routing_overhead`, etc. |
| test_dashboard.py | `pytest.importorskip("streamlit")` ; fonctions pures de `dashboard/ui.py` et parcours `AppTest` (cartes, onglets, cache, CSV, curseur désactivé, local/global) |

---

## 4. Dashboard (`dashboard/`)

- **`ui.py`** :
  - constantes de la charte ;
  - `_CSS` injecté (polices Google, cartes `stMetric`) ;
  - fonctions pures testées (`format_fr`, `format_value`, `compare_table`, `reading_sentence`, `pareto_sentence`, `scaling_summary`, `scaling_sentence`, `observables_*`, `hardware_table`, `hardware_sentence`, `to_csv`, `log_ticks`…) ;
  - graphiques matplotlib : `fidelity_figure`, `expressibility_figure`, `pareto_figure`, `_two_series_figure`, qui sert à `scaling_figure` et à `observables_figure`. `_scaling_axes` gère l'axe log, avec `LogLocator(numticks=50)` : en dessous du nombre de décades visibles, les graduations mineures disparaissent ;
  - `CIRCUIT_STYLE` sert au dessin Qiskit mpl. Piège : `displaycolor["target"][0]` est la couleur du « + » de la cible CNOT.
- **`app.py`** :
  - fonctions de calcul en `@st.cache_data`, avec des paramètres primitifs pour que la clé de cache soit hachable ;
  - widgets avec `key=` ; résultats gardés dans `st.session_state` ;
  - `run_scaling` **crée et vide sa barre de progression à l'intérieur** de la fonction en cache. Sinon, au rejeu du cache, Streamlit lève `CacheReplayClosureError` ;
  - les widgets qui en contrôlent d'autres sont lus en premier, dans leur colonne : le mode avant le curseur Couches, la case « Comparer » avant l'observable ;
  - `sys.path.insert` du dossier, pour `import ui`.

---

## 5. API (`api/stochastiq_api/`)

Installation : `pip install -e ./api[dev]`. Lancement depuis `api/` : `uvicorn stochastiq_api.main:app`. Tests : `cd api; pytest` (`testpaths=["tests"]`, `conftest.py` importé directement).

### 5.1 Socle

- **`config.py`** :
  - `Settings(BaseSettings)` lit l'environnement ou un `.env` du dossier courant (`extra="ignore"`) : `env="dev"`, `secret_key=DEFAULT_SECRET_KEY` (« dev-secret-a-remplacer-hors-developpement », 41 caractères pour éviter l'avertissement de longueur de PyJWT), `database_url="sqlite:///./stochastiq.db"`, `cors_origin="http://localhost:5173"`, `jwt_expire_hours=12`, `run_timeout_seconds=600` ;
  - `check()` lève `RuntimeError` hors `dev` si le secret est celui par défaut ou fait moins de 32 caractères.
- **`db.py`** :
  - `Base(DeclarativeBase)` ;
  - `utcnow()` renvoie une date UTC **sans fuseau**, car SQLite ne le conserve pas. Il faut l'utiliser partout pour les comparaisons de dates ;
  - `make_engine` active `check_same_thread=False` et `PRAGMA foreign_keys=ON` pour les cascades SQLite ;
  - `alembic_config(url)` et `upgrade_database(url)` appliquent les migrations par programme ;
  - `get_db` ouvre une session par requête via `request.app.state.sessionmaker`.
- **`models.py`** :
  - User : email unique et indexé ;
  - Project : slug unique, `memberships` avec cascade ;
  - Membership : clé primaire composite (project_id, user_id), role, title ;
  - Invitation : token unique, status, expires_at ;
  - Run : params et result en JSON, status indexé ;
  - Comment, ActivityEvent : payload JSON, relation user ;
  - PinnedCircuit : unicité (project_id, ansatz, n_qubits, layers) ;
  - Machine : provider et label, **aucune colonne de secret**.

  Les clés étrangères des projets sont en `ondelete="CASCADE"`, celles vers `users.id` en `SET NULL`.
- **Migrations** (`migrations/`) :
  - `env.py` prend l'URL de `Settings()` en ligne de commande (si `config.config_file_name` est défini), sinon celle passée par `upgrade_database`. `render_as_batch=True` pour SQLite ;
  - `versions/0001_initial.py` (users, projects, memberships, invitations) et `0002_runs.py` (runs, comments, activity_events, pinned_circuits, machines) ont été autogénérés puis nettoyés ;
  - `tests/test_migrations.py` vérifie que `compare_metadata` ne trouve **aucun écart** entre les migrations et les modèles. Pour toute nouvelle colonne : `alembic revision --autogenerate -m "..." --rev-id 0003` depuis `api/`, avec `DATABASE_URL` pointant vers une base temporaire déjà migrée.
- **`main.py`** :
  - `create_app(settings=None)` appelle d'abord `settings.check()` ;
  - lifespan : `upgrade_database`, `mark_orphans_failed`, puis création de `app.state.runs = RunManager(...)` ; à l'arrêt, `runs.shutdown()` et `engine.dispose()` ;
  - CORS sur `[settings.cors_origin]`, méthodes GET, POST, PATCH et DELETE, en-têtes Authorization et Content-Type ;
  - inclusion des 7 routeurs ;
  - filtre `MaskInvitationTokens` sur `uvicorn.access` ;
  - `app = create_app()` au niveau du module, pour uvicorn.

### 5.2 Sécurité et droits

- **`security.py`** :
  - `PasswordHasher()` d'argon2-cffi, dans la variable de module `_hasher`. Les tests la remplacent par des paramètres allégés via une fixture `autouse`, ce qui divise la durée des tests par 4 ;
  - `create_token` (sub = id, iat, exp) et `decode_token` (renvoie None en cas d'erreur) ;
  - `MaskInvitationTokens` réécrit `record.args` et `record.msg` avec la regex `(/invitations/)[^/\s?"]+`.
- **`roles.py`** : `Role = Literal[...]`, `ROLES`, `ROLE_LABELS`, `PERMISSIONS` (liste d'actions avec libellé et rôle minimal, **source unique** de la matrice), `MIN_ROLE`, `has_role`.
- **`deps.py`** :
  - `get_current_user` lit `HTTPBearer(auto_error=False)`, puis 401 avec `WWW-Authenticate: Bearer` ;
  - `require_role(min_role)` renvoie une dépendance qui prend `project_id` du chemin, puis donne 404 si la personne n'est pas membre et 403 si son rôle est insuffisant. Elle retourne un `ProjectAccess(project, user, membership)`.

  Pour ajouter une route protégée : `access: ProjectAccess = Depends(require_role(MIN_ROLE["action"]))`. Ajouter l'action dans `PERMISSIONS` si elle est nouvelle, puis dans `web/src/lib/roles.ts DEFAULT_PERMISSIONS`.

### 5.3 Schémas

- **`schemas.py`** :
  - `Input` (`extra="forbid"`, **pas** de nettoyage global des espaces, pour ne pas toucher aux mots de passe) et `Output` (`from_attributes`) ;
  - type `Email` : `AfterValidator(_email)` avec `validate_email(..., check_deliverability=False, test_environment=True)`, ce qui accepte `.test` ; résultat en minuscules ;
  - type `Name` : espaces retirés aux extrémités, 1 à 100 caractères ;
  - schémas RegisterIn, LoginIn, TokenOut, UserOut, ProjectIn, ProjectPatch, ProjectOut (+ role), MemberOut, MemberPatch, InvitationIn, InvitationOut (+ link) et InvitationPublic.
- **`run_schemas.py`** :
  - `AnsatzName = Literal[ANSATZ_NAMES]` et `TopologyName`, construits dynamiquement depuis la bibliothèque via `catalog.py` ;
  - bornes en `Annotated[int, Field(ge, le)]` ;
  - `DiagnosticParams`, `CompareParams` (1 à 7 ansatz uniques), `ScalingParams` (1 à 4 ansatz, validateur qubit_min ≤ qubit_max, `compare_observables`) et `HardwareParams` ;
  - `RunIn` est une **union discriminée par `kind`** (`Field(discriminator="kind")`) ;
  - `MachineIn` porte un `model_validator(mode="before")` qui refuse `SECRET_FIELDS` avec un message explicite ;
  - modèles de sortie : RunSummary, RunOut, RunPage, CommentOut, ActivityOut, ActivityPage, PinOut et MachineOut.

### 5.4 Routeurs (`routers/`)

| Fichier | Contenu |
|---|---|
| `meta.py` | `/health`, `/roles` |
| `auth.py` | `/auth/register` (409 si l'e-mail existe déjà), `/auth/login` (401), `/me` |
| `projects.py` | `_slugify` (NFKD, ascii), `_unique_slug` (suffixes -2, -3…) ; liste, création (Membership owner), lecture, PATCH, DELETE ; membres : liste, PATCH (protection du dernier owner via `_owner_count`, événement `role_changed` avec l'ancien et le nouveau rôle), DELETE |
| `invitations.py` | `_refresh_status` (pending → expired), `_out` (lien = `cors_origin + /invitations/ + token`) ; création (vérifie membre ou invitation en attente, `secrets.token_urlsafe(32)`, +7 jours, événement `member_invited`) ; liste ; révocation ; lecture publique ; acceptation (410, 409, 403, puis Membership + statut accepted + événement `member_joined`) |
| `catalog.py` | `/ansatz`, `/ansatz/{name}/structure` (Query 2–8 et 1–8, 404 si nom inconnu, ajoute `stats`), `/topologies` |
| `runs.py` | POST (compte les runs pending/running de l'utilisateur, 429 au-delà de 2, crée le Run et l'événement `run_launched`, commit puis `app.state.runs.submit`) ; liste (filtres et pagination, alias `status`) ; détail ; commentaires (événement `comment_added` avec un extrait de 120 caractères) |
| `collaboration.py` | activité ; épingles (409 en doublon, événement `circuit_pinned`) ; machines (key_manager, événement `machine_added`) |

`events.py` contient `EVENT_TYPES` et `record(db, project_id, user_id, type, payload)`, qui ajoute l'événement à la transaction en cours avec un `assert` sur le type. Pour un nouvel événement, l'ajouter ici et dans `web/src/lib/activity.ts`.

### 5.5 Exécution des runs (`jobs.py`, `runner.py`)

- **`runner.py`** est exécuté **dans le processus de calcul**, sans accès à la base :
  - `execute(kind, params)` appelle `KINDS[kind](params)`, puis `to_json` (récursif : numpy vers Python, `NaN` et infinis vers None) ;
  - `_compare` calcule la colonne `pareto` à partir de (expressibility, gradient_variance_active) ;
  - `_scaling` boucle sur les observables (`["Z0","Zall"]` si `compare_observables`) et sur les ansatz, puis ajoute `fit_active` et `fit_all`.
- **`jobs.py`** :
  - `mark_orphans_failed` met à jour en masse les runs pending ou running ;
  - `RunManager` :
    - `ThreadPoolExecutor(max_workers=2)` joue le rôle de dispatcher ;
    - `submit(run_id)` lance `_run` dans un fil, qui relit le run, le passe en running avec `started_at`, puis crée **un `ProcessPoolExecutor(max_workers=1)` dédié** et attend `.result(timeout)` ;
    - en cas de dépassement, `_kill` appelle `terminate_workers()` (Python ≥ 3.14) ou, à défaut, `kill()` sur chaque processus de l'attribut privé `_processes`, puis `shutdown(cancel_futures=True)`. L'erreur enregistrée est « Durée maximale dépassée (10 minutes). » ;
    - en cas d'exception, le message court `Type : message` est enregistré, sans trace ;
    - `_finish` écrit le statut, le résultat, l'erreur et `finished_at`, puis l'événement `run_done` ou `run_failed` ;
    - `shutdown()` tue les exécuteurs actifs.
  - Pourquoi un exécuteur par run : un calcul de la bibliothèque ne peut pas être interrompu, et il faut pouvoir tuer un run sans toucher l'autre calcul.
- **`catalog.py`** contient `ANSATZ_INFO` (affichage, description française, formule des paramètres), `TOPOLOGY_LABELS`, `ANSATZ_NAMES` et `TOPOLOGY_NAMES` (calculés depuis la bibliothèque), ainsi que `ansatz_catalog()` et `topology_catalog()`.

### 5.6 Tests de l'API (`api/tests/`, 171 tests)

- **`conftest.py`** :
  - fixture `fast_hashing` (autouse) ;
  - `settings(tmp_path)` : `env="test"`, secret long, base SQLite dans tmp, `cors_origin="http://front.test"` ;
  - `client` : `TestClient(create_app(settings))` en contexte, ce qui lance le lifespan et donc les migrations ;
  - aides `register()` (retourne les en-têtes Authorization), `create_project()` et `add_member()` (invitation puis acceptation par un nouveau compte) ;
  - fixture `team` : un membre par rôle, plus un `outsider`.
- **`test_roles.py`** et **`test_collaboration.py`** : matrices paramétrées action × rôle. Selon `has_role`, on attend un code < 300 ou un 403 ; pour l'extérieur, un 404.
- **`test_runs.py`** :
  - cycle de vie des 4 kinds, avec 2 qubits et 50 échantillons ; `wait_run` interroge l'API toutes les 0,5 s ;
  - bornes refusées (422, aucun run créé) ;
  - 429 (runs pending et running insérés directement en base) ;
  - dépassement de durée avec `run_timeout_seconds=0.5` et 5000 échantillons ;
  - orphelins : deux `create_app` successifs sur la même base ;
  - filtres et pagination, isolation.
- Autres fichiers : test_auth (CORS, masquage des jetons, argon2, espaces du mot de passe conservés, secret refusé), test_invitations, test_projects et test_migrations.

---

## 6. Application web (`web/`)

Pile : Vite 5.4, React 18.3, TypeScript 5.6 (`strict`, `noUnusedLocals`), React Router 6.28 (options `future` v7 activées dans `BrowserRouter` et dans les `MemoryRouter` des tests), Recharts 2.13, Vitest 2.1, React Testing Library 16, jsdom, Playwright 1.49.1. Pas de framework CSS.

### 6.1 Socle

- **`src/main.tsx`** : `BrowserRouter`, puis `AppRoutes`, avec l'import de `styles/theme.css`.
- **`src/App.tsx`** :
  - `AuthProvider` autour des `Routes` ;
  - routes publiques `/login`, `/register`, `/invitations/:token` ;
  - `/projects` dans `RequireAuth` et `AppLayout` ;
  - `/projects/:projectId/*` dans `RequireAuth` et `ProjectLayout` ;
  - les écrans scientifiques sont chargés en **`React.lazy`** et enveloppés dans `Screen` (Suspense), pour isoler Recharts dans un fichier séparé et éviter l'avertissement de bundle de plus de 500 Ko.
- **`src/styles/theme.css`** :
  - variables de la charte, `.app` en grille `240px minmax(0, 1fr)` ;
  - **`minmax(0, 1fr)` et `main.content { min-width: 0 }` sont indispensables** : sans eux, la page débordait de 133 px à 390 px de large (défaut trouvé par Playwright) ;
  - classes : card, grid-3, row, tabs, pill (avec running, done, failed ; failed est en corail sur fond blanc pour le contraste), help (bouton « ? » de 44 px), state, alert, info, activity, auth-page, visually-hidden ;
  - media query à 800 px.
- **`src/api/client.ts`** :
  - `API_URL` vient de `VITE_API_URL` (défaut `http://localhost:8000`) ;
  - jeton en variable de module (`setToken`) ;
  - `request()` ajoute `Authorization`. En cas d'échec réseau, `ApiError(0, "API injoignable…")`. Une réponse 204 donne undefined. Les erreurs deviennent `ApiError(status, message)` ; pour une liste pydantic, on garde le premier message préfixé du champ ;
  - **une réponse 401 avec un jeton présent appelle `onUnauthorized`** ;
  - objet `api` avec get, post, patch et delete.
- **`src/api/types.ts`** : types écrits à la main d'après l'OpenAPI. Les tenir à jour quand l'API change.
- **`src/auth/AuthContext.tsx`** :
  - le jeton est conservé dans `sessionStorage` sous la clé `stochastiq.token` (le compromis est expliqué en commentaire) ;
  - au montage, on relit le jeton, puis `/me` ;
  - `login` et `register` (qui enchaîne sur `login`), `logout` ;
  - le gestionnaire de 401 vide la session et navigue vers `/login?next=…` ;
  - `useAuth()`.
- **`src/lib/`** :

  | Fichier | Contenu |
  |---|---|
  | `roles.ts` | `ROLES`, `ROLE_LABELS`, `DEFAULT_PERMISSIONS` (copie de l'API, utilisée tant que `/roles` n'est pas chargé), `hasRole`, `minRoleFor`, `can`, `deniedReason` |
  | `format.ts` | `formatFr` (évite « -0,00 »), `formatMetric` (4 décimales), `formatFactor` (×1,00), `formatPercent`, `formatDateTime` (ajoute « Z » aux dates sans fuseau de l'API, puis `fr-FR`) |
  | `activity.ts` | `describeEvent` : phrase française par type d'événement |
  | `useAsync.ts` | chargement, erreur, données et `reload`, ignorés après démontage |
  | `reading.ts` | **copie fidèle des règles du dashboard** : `ANSATZ_LABELS`, `ansatzLabel`, `compareSentence`, `paretoSentence`, `PARETO_NOTE`, `isNetDecay`, `layersLine`, `scalingSentence`, `observablesSentence`, `logTicks`, `logTickLabel`, et les constantes (seuils 0,8, 0,9 et 0,1, phrases) |
  | `csv.ts` | `toCsv` (commentaire `#`, échappement des guillemets et virgules, `APP_VERSION`), `downloadCsv` (Blob et lien temporaire) |
  | `runs.ts` | `LIMITS` (mêmes bornes que l'API), `boundErrors` (messages « Qubits : entier de 2 à 8. », avec une espace fine insécable U+202F dans « 5 000 » via `toLocaleString`), `launchRun`, `useRunPolling` (setTimeout de 2 s, arrêt à done ou failed, nettoyage au démontage) |

### 6.2 Composants (`src/components/`)

- **`common.tsx`** :
  - `Logo`, `Loading` (`role="status"`), `ErrorState` (`role="alert"`, bouton Réessayer), `Empty`, `StatusPill` ;
  - **`GuardedButton`** : actif si `allowed`. Sinon, il est enveloppé dans un `<span title=raison>` avec `disabled` et `aria-describedby`, qui pointe vers un texte masqué portant la raison.
- **`ProjectContext.tsx`** :
  - `ProjectProvider` charge `/projects/:id` et `/roles`, puis fournit `{project, permissions, can(action), reason(action), reload}` ;
  - `useProject()` ;
  - `ProjectContextProvider` permet d'injecter le contexte dans les tests.
- **`Layout.tsx`** : `Sidebar` (liste `PROJECT_NAV`), `AppLayout`, `ProjectLayout` (enveloppé dans ProjectProvider).
- **`MembersTable.tsx`** : sélecteurs de rôle et champs de titre (enregistrement à la perte de focus), désactivés avec infobulle sans droit ; bouton « Retirer » en `GuardedButton`.
- **`ActivityList.tsx`** : liste `aria-label="Fil d'activité"` ; état vide.
- **`science.tsx`** : `useAnsatzCatalog`, `useTopologies`, `MetricCard` (bouton d'aide `.help` focalisable, avec `title`, `aria-label` et description masquée), `CsvButton`, `RunStatusBanner`, `CommentsPanel` (droit `comment`), `NumberField` (`aria-invalid`, message d'erreur ou note).
- **`charts.tsx`** :
  - `Frame` : avec `width`, taille fixe (indispensable dans jsdom) ; sinon `ResponsiveContainer` ;
  - `FidelityHistogram` (ComposedChart : Bar violette, Line corail) et `histogramRows` ;
  - `ParetoScatter` : deux séries (front et autres), `ErrorBar` x et y si `_std`, `LabelList` avec les noms d'affichage ;
  - `ScalingChart` : `YAxis scale="log"`, `ticks=logTicks(...)`, domaine étendu de 15 %, `tickFormatter=logTickLabel`, grille horizontale ; un `Line` par série, avec ses propres données, `strokeDasharray` (pointillé « 6 4 », mixte « 9 3 2 3 ») et un marqueur personnalisé `MarkerShape` (rond, carré, triangle ou losange ; creux si la série n'est pas en trait plein) ; légende par `payload` ;
  - `SERIES_STYLES` et `COLORS`.
- **`CircuitSvg.tsx`** : SVG avec des espacements fixes (fils tous les 48 px, colonnes de 56 px). `role="img"` et un `aria-label` qui résume le circuit. Les attributs `data-gate` servent aux tests.

### 6.3 Pages (`src/pages/`)

| Fichier | Contenu |
|---|---|
| `AuthPages.tsx` | `LoginPage`, `RegisterPage` (`registerErrors` pure, erreurs affichées après soumission, `aria-describedby`), `RequireAuth`. `useNext()` n'accepte que des chemins internes (`/` mais pas `//`) |
| `InvitationPage.tsx` | gère tous les cas (non connecté, mauvais e-mail, statut non pending, acceptation, puis navigation vers le projet) |
| `ProjectsPage.tsx`, `ProjectPage.tsx` | `KIND_LABELS` est exporté (et réutilisé par JobsPage) ; onglets en `role="tablist"` |
| `TeamPage.tsx` | `PermissionMatrix` (Oui/Non), `InviteForm` (lien copiable via `navigator.clipboard`, avec repli manuel), `PendingInvitations` (rechargée par un compteur `version`), changements de rôle et de titre |
| `DiagnosticPage.tsx` | `DiagnosticForm`, `OBSERVABLE_LABELS`, `validateDiagnostic`, `DiagnosticFormFields` ; le run courant est dans `?run=` (`useSearchParams`), ce qui rend un résultat partageable par URL ; épinglage |
| `ComparePage.tsx` | `CompareTable` (moyenne ± écart-type) et page |
| `AnsatzPage.tsx` | charge `/ansatz/{name}/structure` (avec `stats`) |
| `BarrenPage.tsx` | `scalingLines(series, compareObservables)` construit les courbes ; la page assemble le formulaire, le tableau et les phrases |
| `JobsPage.tsx` | `RunsList`, `hardwareRows`, `HardwareTab` (run hardware, `?tab=materiel&run=`), `MachinesSection` (liste seulement si key_manager ou plus), `JobsPage`, `RunDetailPage` (`SCREENS` relie chaque kind à l'écran de son résultat) |

### 6.4 Tests du front

- **Configuration** : `vite.config.ts` (bloc `test` : jsdom, globals, `setupFiles: src/test/setup.ts`, qui charge jest-dom et vide le DOM et `sessionStorage`). `npm run build` lance `tsc -b`, qui **vérifie aussi les types des tests**. Les mocks doivent donc être typés, par exemple `vi.fn((url: string, _init?: RequestInit) => …)`.
- **`auth.test.tsx`** : connexion (suivi de `next`, jeton stocké, refus de redirection externe), erreur de l'API, validation à l'inscription. `fetch` est simulé avec `vi.stubGlobal`.
- **`team.test.tsx`** : tableau des membres, boutons désactivés avec description accessible, matrice, `describeEvent`, formatage.
- **`reading.test.ts`** : mêmes cas que `tests/test_dashboard.py`.
- **`science.test.tsx`** : graphiques (sélecteurs `.recharts-bar-rectangle`, `.recharts-line-curve`, `.recharts-scatter-symbol`), SVG, bornes, `DiagnosticPage` en contexte injecté.
- **Bout en bout** :
  - `playwright.config.ts` démarre `..\.venv\Scripts\uvicorn` (modifiable par `E2E_UVICORN`) sur le port 8010, avec une base temporaire, et `npx vite` sur le port 5180 ;
  - `e2e/parcours.spec.ts` : un seul parcours. Avec `SCREENSHOT_DIR=…`, il enregistre 7 captures. Il vérifie l'absence de débordement horizontal à 390 px ;
  - piège : un `<select>` placé dans son `<label>` a un nom accessible qui inclut l'option choisie (« Rôle Lecteur »). Il faut donc des sélecteurs du type `getByLabel(/^Rôle/)`, limités au bon formulaire.

---

## 7. Déploiement et scripts

- **`api/Dockerfile`** :
  - contexte de build : la **racine** du dépôt ;
  - copie `pyproject.toml`, `README.md`, `LICENSE`, `src`, `api` et `scripts`, puis `pip install ./ ./api` ;
  - utilisateur `stochastiq` (uid 1000), `/data` ;
  - `HEALTHCHECK` en Python (urllib, sans curl) ;
  - `CMD uvicorn` sur 0.0.0.0:8000.
- **`web/Dockerfile`** : build multi-étapes, `node:22-alpine` (`npm ci`, `ARG VITE_API_URL`, build), puis `nginx:1.27-alpine` avec `nginx.conf` (`try_files … /index.html`).
- **`docker-compose.yml`** :
  - `env_file` avec `path: .env, required: false` (Compose ≥ 2.24), pour que `docker compose config` passe sans `.env` ;
  - `DATABASE_URL` forcé vers `/data/stochastiq.db` (volume `api-data`) ;
  - `web` dépend de `api` en `service_healthy` ; ports 8000 et 5173.
- **`.dockerignore`** exclut `.git`, `.venv`, `web`, `dashboard`, `examples`, `tests`, `docs`, les bases et `.env`. `web/.dockerignore` exclut `node_modules` et `dist`.
- **`scripts/seed_demo.py`** :
  - utilise `TestClient(create_app(settings))` : l'API tourne en processus, avec un vrai ordonnanceur. C'est pourquoi `httpx` fait partie des dépendances principales de l'API ;
  - `--database-url` est facultatif ;
  - refuse de tourner si `membre1` peut déjà se connecter ;
  - lance les runs un par un, en attendant chaque résultat (limite de 2 runs en cours) ;
  - affiche les comptes et le mot de passe.
- **CI** (`.github/workflows/tests.yml`) :
  - job `test` : bibliothèque, matrice 3.10–3.12, `pip install -e ".[dev]"`, `pytest` ; dashboard et PennyLane ignorés via `importorskip` ;
  - job `api` : 3.12 ;
  - job `web` : Node 22, `npm ci`, test, build.

---

## 8. Recettes pour continuer

- **Vérification complète** (PowerShell, depuis la racine) :
  - `.venv\Scripts\python -m pytest` (environ 2 min) ;
  - `cd api; ..\.venv\Scripts\python -m pytest` (environ 2 min) ;
  - `cd web; npm test; npm run build; npx playwright test` ;
  - `docker compose config`.
- **Lancer l'application** : voir le rapport 1, §8. Penser à remplir `api/stochastiq.db` avec le script de démo.
- **Ajouter un type de run** :
  1. schéma de paramètres dans `run_schemas.py`, et entrée dans l'union `RunIn` ;
  2. fonction dans `runner.py`, ajoutée à `KINDS` ;
  3. `RunKind` dans `web/src/api/types.ts`, `KIND_LABELS`, `SCREENS` (JobsPage) et `activity.ts` ;
  4. tests dans `api/tests/test_runs.py` (dict `SMALL`).
- **Ajouter un champ en base** : modifier le modèle, autogénérer la migration 0003, vérifier `test_migrations.py`.
- **Ajouter un écran web** : page dans `src/pages`, route dans `App.tsx` (en `lazy` si elle utilise Recharts), lien dans `PROJECT_NAV` (Layout).
- **Changer une règle de lecture** : la modifier **aux deux endroits**, `dashboard/ui.py` et `web/src/lib/reading.ts`, ainsi que leurs tests respectifs (`tests/test_dashboard.py`, `web/src/test/reading.test.ts`).
- **Commits** : branche dédiée, un commit par bloc, message en français terminé par la ligne `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Pas de push, pas de modification de `main`. Une nouvelle release se fait sur une branche `release/v0.3` créée depuis `release/v0.2`, avec des fusions `--no-ff`, les tests verts à chaque fusion, puis un tag local.
