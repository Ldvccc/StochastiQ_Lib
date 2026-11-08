# Rapport 1 : fonctionnalités de StochastiQ (état au 8 novembre 2026, version 0.3.0)

Ce rapport décrit **ce que fait** le projet, écran par écran et fonction par fonction, ainsi que les règles métier, les conventions imposées par l'auteur et l'état du dépôt. Le rapport 2 (`docs/RAPPORT_CODE.md`) explique **comment** c'est codé. Les deux ensemble suffisent pour reprendre le travail sans autre contexte.

---

## 1. Le projet en bref

- **Objet** : StochastiQ est un prototype universitaire de diagnostic d'ansatz (circuits quantiques paramétrés) pour les machines de Born quantiques (QCBM), construit sur Qiskit. Depuis la v0.3, un client y apporte aussi sa distribution et ses ansatz, les entraîne en simulation (avec ou sans bruit), les compare à des références classiques simples et reçoit une prédiction et une recommandation (section 12). Pour un circuit, il mesure :
  - l'expressibilité ;
  - la capacité d'intrication ;
  - la variance du gradient (détection des plateaux stériles) ;
  - le coût de transpilation sur des topologies matérielles.
- **Dépôt** : `C:\Users\ldvcb\Desktop\Sto\StochastiQ_Lib`, remote `https://github.com/Ldvccc/StochastiQ_Lib`. Rien n'a jamais été poussé depuis le début du travail.
- **Contexte** : prototype universitaire, **pas une application de production**. Cette mention figure dans le README et doit y rester.
- **Quatre parties** :
  1. **Bibliothèque Python** `stochastiq` (`src/stochastiq/`, version 0.2.0) : tous les calculs génériques, **aucune dépendance web**.
  2. **API FastAPI** (`api/`, paquet `stochastiq_api`, version 0.3.0) : comptes, projets, rôles, invitations, problèmes, ansatz personnalisés, runs, activité ; base de résultats et IA dans `api/stochastiq_api/ml/`.
  3. **Application web React** (`web/`, version 0.3.0) : écrans d'équipe et écrans scientifiques.
  4. **Dashboard Streamlit** (`dashboard/`) : outil local d'exploration, **hors application web**.
- **Sens des dépendances** : l'API importe la bibliothèque, **jamais l'inverse**. Le front ne parle qu'à l'API.

---

## 2. Conventions imposées par l'auteur (à respecter dans toute suite)

- **Langue** : interface, messages d'erreur, docstrings, commentaires, messages de commit **et rapports à l'auteur** en **français**.
- **Nombres affichés** : notation française, avec **virgule décimale**. En règle générale, 4 décimales pour les métriques, 2 pour les surcoûts (« ×1,00 »), 1 pour les pourcentages (« 33,3 % »). Pas de notation scientifique, sauf sur l'axe logarithmique sous 0,0001 (« 1e-5 », « 1,5e-5 »). L'API et le CSV, eux, utilisent des nombres JSON standard, avec point décimal.
- **Style** : pas d'emoji, pas de point d'exclamation, nulle part.
- **Charte StochastiQ** :

  | Variable | Couleur | Usage |
  |---|---|---|
  | surface | #F6F5FB | fond lavande |
  | surface-raised | #FFFFFF | cartes |
  | line | #E1DFEE | traits, grilles |
  | ink | #14163F | texte principal |
  | ink-muted | #585B7A | texte secondaire |
  | violet | #5B4BFF | actions, circuit |
  | violet-soft | #ECE9FF | fonds légers |
  | on-violet | #FFFFFF | texte sur violet |
  | coral-strong | #D42A45 | **réservé** aux courbes de référence (Haar) et aux alertes |
  | night | #14163F | |

  - Polices : titres Space Grotesk 700, texte Instrument Sans, chiffres JetBrains Mono (Google Fonts).
  - Rayons 6 / 12 / 20 px, une seule ombre de carte, anneau de focus violet de 2 px.
  - Cibles tactiles ≥ 44 px, contraste texte/fond ≥ 4,5:1.
  - Logo : le texte « StochastiQ », avec le Q en violet.
  - Le texte corail ne doit **jamais** être posé sur violet-soft (contraste mesuré : 4,19:1).
- **Code** : docstrings en français, type hints partout, argument `seed` dans toute fonction aléatoire, `np.random.default_rng(seed)`.
- **Plateforme** : Windows et PowerShell d'abord ; pas de script uniquement bash ; commandes documentées en PowerShell. Docker est optionnel, mais il est installé et fonctionne sur la machine.
- **Git** :
  - une branche par lot de travail, un commit par bloc fonctionnel, messages en français ;
  - chaque message se termine par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` ;
  - **ne jamais pousser** et **ne jamais toucher à `main`** ;
  - les branches de release (`release/v0.1`, `release/v0.2`, `release/v0.3`) regroupent le travail par fusions `--no-ff` ; les tags sont locaux (`v0.1.0`, `v0.2.0`, `v0.3.0`) ;
  - v0.3 : une branche `feature/` par jalon, chacune partant de la précédente ; **le code d'un jalon ne s'écrit que sur sa propre branche** ; un commit doit correspondre exactement à ce qui a été testé.
- **Méthode** :
  - lire le code existant avant de modifier ;
  - ne coder que ce qui est demandé ;
  - signaler toute dérogation ;
  - ne jamais corriger « au hasard » un écart inexpliqué : le montrer ;
  - si un jalon échoue après deux tentatives de correction, s'arrêter, décrire le blocage et proposer une solution ;
  - mesurer avant tout calcul de plus de 15 minutes ; si l'estimation dépasse 2 heures, s'arrêter et demander ;
  - aucune valeur inventée ;
  - **sécurité** : ne jamais exécuter de code Python fourni par un client ; toute entrée client passe par pydantic, avec des tailles bornées.
- **Rapports de fin de tâche** : tests lancés avec leur résultat affiché, liste de ce qui n'a pas pu être vérifié (en particulier le rendu visuel), liste des dérogations.
- **Hors périmètre (ne pas coder)** (l'entraînement de QCBM et le bruit simulé y sont entrés en v0.3, par dérogation) :
  - connexion à de vraies machines (IBM, Origin) ; la collecte IBM (jalon 9) est facultative et **ne se commence pas sans accord explicite de l'auteur** ;
  - envoi d'e-mails ;
  - paiement ;
  - mode multi-organisations ;
  - stockage de clés de machines.

---

## 3. Bibliothèque `stochastiq` (calculs)

API publique (`from stochastiq import ...`) : `expressibility`, `fidelity_histogram`, `entangling_capability`, `circuit_stats`, `gradient_variance`, `gradient_variance_details`, `hardware_cost`, `list_topologies`, `build_ansatz`, `list_ansatz`, `ansatz_structure`, `compare`, `pareto_front`, `gradient_scaling`, `fit_decay`.

### 3.1 Les 7 ansatz (`build_ansatz(name, n_qubits, layers)`, `list_ansatz()`)

Définis « d'après le rapport QCBM Lab, section 2.4 ». Ordre de `list_ansatz()` : basic_entangler, strongly_entangling, hardware_efficient, rotation_only, all_to_all, brick_wall, data_reuploading.

Structure commune : par couche l, on applique les k rotations de l'ansatz sur chaque qubit j, puis les CNOT. L'indice d'un paramètre est `((l*n)+j)*k + r` (tableau de forme (L, n, k) aplati, `ParameterVector("θ")`).

| Nom | Affichage | Rotations | CNOT par couche | Paramètres |
|---|---|---|---|---|
| basic_entangler | BasicEntangler | RX | anneau i→(i+1)%n si n>2 ; un seul CNOT(0,1) si n=2 ; aucun si n=1 | L·n |
| strongly_entangling | StronglyEntangling | RZ, RY, RZ | CNOT(i,(i+r)%n) pour tout i, r=(l%(n−1))+1 ; aucun si n=1 | 3·L·n |
| hardware_efficient | HardwareEfficient | RY, RZ | chaîne i→i+1 | 2·L·n |
| rotation_only | RotationOnly | RY | aucun | L·n |
| all_to_all | AllToAll | RX, RY, RZ | toutes les paires i<j | 3·L·n |
| brick_wall | BrickWall | RY, RZ | couche paire : i=0,2,4… ; impaire : i=1,3,5… (i+1<n) | 2·L·n |
| data_reuploading | DataReuploading | RZ, RY, RZ | anneau i→(i+1)%n ; **pour n=2 : CNOT(0,1) puis CNOT(1,0)** | 3·L·n |

Ces circuits sont vérifiés contre PennyLane (option `verify`, `tests/test_ansatz_pennylane.py`, 63 cas, écart ~1e-16) :
- basic_entangler contre `BasicEntanglerLayers(rotation=qml.RX)` ;
- strongly_entangling contre `StronglyEntanglingLayers` ;
- les autres contre des circuits écrits porte par porte.

`ansatz_structure(name, n_qubits, layers)` renvoie le circuit en colonnes, pour le dessin web. Une colonne par rotation r d'une couche (tous les qubits), puis une colonne par CNOT. Format : `{"n_qubits", "layers", "columns": [{"gates": [{"type": "RX"|"RY"|"RZ"|"CNOT", "qubits": [...], "param_index": int|None}]}]}`.

### 3.2 Métriques

- **Expressibilité** (`expressibility(ansatz, n_samples=2000, n_bins=75, seed=None)`, Sim et al. 2019, arXiv:1905.10876) :
  - divergence KL entre l'histogramme des fidélités |⟨ψ(θ)|ψ(φ)⟩|² de paires aléatoires et la distribution de Haar P(F)=(d−1)(1−F)^(d−2), avec d=2^n ;
  - probabilités par classe calculées avec la CDF 1−(1−F)^(d−1) ;
  - ε=1e-12 pour éviter log(0) ;
  - **plus bas = plus expressif** ;
  - `fidelity_histogram` renvoie `{"edges", "circuit", "haar"}`.
  - Valeurs de référence : `expressibility(real_amplitudes(4, reps=3), n_samples=1000, seed=0)` = **0,1416** (0,3249 avec reps=1).
- **Intrication** (`entangling_capability(ansatz, n_samples=2000, seed=None)`) : mesure de Meyer-Wallach moyenne, Q = 2(1 − moyenne des Tr(ρ_k²)), comprise entre 0 et 1.
- **Statistiques** (`circuit_stats(ansatz)`) : transpilation vers ry, rz, rx, cx, h au niveau 0, puis n_qubits, n_parameters, depth, n_two_qubit_gates et gate_counts.
- **Variance du gradient** (`gradient_variance_details(ansatz, n_samples=200, observable="Z0", seed=None)`) :
  - règle du décalage de paramètre (f(θ+π/2) − f(θ−π/2))/2, calculée pour **chaque** paramètre ;
  - variance sur `n_samples` points ;
  - retourne `mean_variance` (tous les paramètres), `active_mean_variance` (paramètres de variance ≥ 1e-12, `nan` s'il n'y en a aucun), `variance_per_parameter`, `n_inactive_parameters` et `inactive_fraction` ;
  - `gradient_variance(...)` renvoie `mean_variance` ;
  - observables :
    - `"Z0"` : coût local, peu de plateau à faible profondeur ;
    - `"Zmean"` : moyenne des Z, somme de termes locaux ;
    - `"Zall"` : produit Z⊗…⊗Z (`SparsePauliOp("Z"*n)`), coût global, plus proche du vrai coût d'un QCBM (TVD, KL) ;
  - les portes paramétrées autres que RX, RY, RZ d'angle égal à un paramètre lèvent une `ValueError`.
- **Paramètres inactifs** : variance < 1e-12. Exemples : un RZ appliqué à |0⟩, ou un paramètre hors du cône causal de l'observable. La moyenne sur tous les paramètres baisse par **dilution** quand leur part augmente. `active_mean_variance` isole le signal.
- **Comparaison** (`compare(ansatz_dict, n_samples=1000, seed=None, n_seeds=1, observable="Z0")`) : DataFrame indexé par nom.
  - Colonnes : n_qubits, n_parameters, depth, n_two_qubit_gates, expressibility, entangling_capability, gradient_variance, gradient_variance_active, inactive_fraction.
  - Tri par expressibilité croissante.
  - Si n_seeds > 1 : moyenne sur les graines seed, seed+1…, et colonnes `<métrique>_std` (ddof=1) pour les 4 métriques. `inactive_fraction` est moyennée, sans `_std`.
- **Front de Pareto** (`pareto_front(points, minimize_x=True, maximize_y=True)`) : liste de booléens « non dominé ». Deux points égaux ne se dominent pas.
- **Plateau stérile** :
  - `gradient_scaling(name, qubit_range=range(2,9), layers=3, layers_mode="fixed"|"linear", n_samples=100, observable="Z0", seed=None, callback=None)` renvoie un DataFrame (n_qubits, layers, n_parameters, mean_variance, active_mean_variance, inactive_fraction) ;
  - `fit_decay(n_qubits, variances)` fait une régression de log(variance) sur n et renvoie factor_per_qubit = exp(pente), r2 et n_points ; `None` s'il y a moins de 3 points valides (> 0).
- **Coût matériel** (`hardware_cost(ansatz, topology="line", seed=None)`, `list_topologies()` = line, ring, full, heavy_hex) :
  - transpilation hors ligne vers cx, rz, sx, x, au niveau 1, avec `seed_transpiler` ;
  - trois niveaux : `before` (circuit d'origine, comme circuit_stats), `basis_only` (graphe complet, sans routage) et `after` (topologie demandée) ;
  - champs à plat conservés : n_two_qubit_gates_before/after, depth_before/after ;
  - `overhead_two_qubit` = after/before (`nan` si before vaut 0) ;
  - `routing_overhead_two_qubit` = after/basis_only, avec `ValueError` si basis_only vaut 0 ;
  - heavy_hex = distance 3, soit 19 qubits ; `ValueError` si l'ansatz est plus grand.

### 3.3 Résultats de référence (4 qubits, 3 couches)

`compare` sur 1000 échantillons et 3 graines :

| ansatz | expressibilité | intrication | var. (tous) | var. (actifs) | inactifs |
|---|---|---|---|---|---|
| data_reuploading | 0,0174 | 0,8338 | 0,0222 | 0,0307 | 27,8 % |
| strongly_entangling | 0,0181 | 0,8159 | 0,0223 | 0,0335 | 33,3 % |
| basic_entangler | 0,0189 | 0,8727 | 0,0364 | 0,0625 | 41,7 % |
| hardware_efficient | 0,0193 | 0,7836 | 0,0312 | 0,0680 | 54,2 % |
| all_to_all | 0,0194 | 0,7906 | 0,0242 | 0,0335 | 27,8 % |
| brick_wall | 0,0314 | 0,6494 | 0,0365 | 0,1251 | 70,8 % |
| rotation_only | 0,7001 | 0 | 0,1251 | 0,5005 | 75,0 % |

Plateau stérile (2 à 6 qubits, 3 couches fixes, 100 échantillons, seed 0) :
- hardware_efficient :
  - Z0, paramètres actifs : facteur ×0,90 (R² 0,49), donc **plat** ;
  - Z0, tous les paramètres : ×0,72, une baisse due à la **dilution** ;
  - Zall : ×0,53 (R² 0,98), décroissance nette.
- data_reuploading : ×0,50 en Z0 et ×0,53 en Zall, décroissance nette dans les deux cas.

---

## 4. Règles de lecture (phrases générées)

Elles existent à l'identique dans le dashboard Streamlit (`dashboard/ui.py`) et dans le web (`web/src/lib/reading.ts`). Les tests reprennent les mêmes cas des deux côtés. **Aucune valeur inventée** : tout vient des résultats.

- **Comparateur** (`reading_sentence` / `compareSentence`) : pour l'expressibilité (plus bas = mieux) et pour l'intrication (plus haut = mieux), un gagnant n'est désigné que si l'écart avec le deuxième dépasse :
  - **10 % de la valeur du meilleur**, avec une seule graine. Sinon : « les différences sont du même ordre que le bruit d'échantillonnage ; relancez avec plusieurs graines » ;
  - **la somme des deux écarts-types**, avec plusieurs graines. Sinon : « « A » et « B » sont indistinguables sur cette métrique ».

  Avec plusieurs graines, la phrase se termine par « Valeurs moyennes sur les graines. ». Elle est vide s'il y a moins de 2 circuits.
- **Front de Pareto** : « Le front de Pareto contient « A », « B » et « C ». » (ou « ne contient que « A ». »), suivi de « Un circuit du front n'est battu par aucun autre sur les deux critères (expressibilité plus basse et variance du gradient des paramètres actifs plus élevée). ». Elle ne contient aucun chiffre. L'axe y montre la variance des **paramètres actifs**, avec une note qui l'explique.
- **Plateau stérile** (`scaling_sentence` / `scalingSentence`) :
  - la conclusion porte sur la série des **paramètres actifs** ;
  - « décroissance exponentielle nette : plateau stérile sur cette plage de qubits, avec cette observable » seulement si facteur < **0,8** et R² > **0,9** ; sinon « pas de décroissance exponentielle nette sur cette plage » ;
  - le mot « plateau stérile » n'apparaît que dans le cas net ;
  - mention de **dilution** si le facteur sur tous les paramètres est **inférieur** au facteur des actifs de plus de **0,1** (sens unique, choisi volontairement) ;
  - avec moins de 3 points : « données insuffisantes » ;
  - une ligne rappelle le mode : « Couches : 3 (fixe). » ou « Couches : égales au nombre de qubits. ».
- **Local contre global** (`observables_sentence` / `observablesSentence`) : facteurs et R² des deux coûts sur les paramètres actifs, puis :
  - global net et local non net : « Le circuit reste entraînable avec un coût local, mais pas avec un coût global ; l'entraînement d'un QCBM sur une distribution complète se rapproche du cas global. » ;
  - les deux nets : « Décroissance exponentielle nette avec les deux coûts sur cette plage. » ;
  - local seul net : « … avec le coût local seulement… » ;
  - aucun des deux : « … ni en local ni en global. ».
- **Matériel** (`hardware_sentence`) : phrase factuelle sur les trois niveaux. « le routage n'ajoute aucune porte à 2 qubits » si after = basis_only.
- **Avertissement d'échantillonnage** : sous 1000 échantillons, « Avec moins de 1000 échantillons, l'expressibilité est surestimée. Comparez uniquement des résultats obtenus avec le même nombre d'échantillons. »
- **Axe logarithmique** (`log_ticks` / `logTicks`) :
  - puissances de dix dans la plage des données, étendues d'une décade du côté le plus proche tant qu'il y en a moins de 2 ;
  - erreur si une valeur est ≤ 0 ;
  - grille horizontale #E1DFEE ;
  - graduations mineures 2 à 9, sans étiquette.

---

## 5. API (`api/`) : fonctionnalités

- **Comptes** :
  - inscription (e-mail unique, en minuscules ; le domaine réservé `.test` est accepté) ;
  - mot de passe ≥ 10 caractères, haché en **argon2id**, **jamais modifié** (pas de nettoyage des espaces) ;
  - connexion avec un **JWT HS256 valable 12 h** ; route `/me`.
- **Sécurité** :
  - `SECRET_KEY` vient de l'environnement. Si `ENV` n'est pas `dev`, l'API refuse de démarrer avec le secret par défaut ou avec un secret de moins de 32 caractères ;
  - CORS limité à `CORS_ORIGIN` ;
  - toutes les entrées sont validées par pydantic, avec refus des champs inconnus ;
  - les jetons d'invitation présents dans les URL sont masqués dans les journaux d'accès (`/invitations/***`) ;
  - jamais de mot de passe ni de jeton dans les journaux.
- **Projets** :
  - création : le créateur devient propriétaire, et un slug unique est généré (`demo`, `demo-2`…) ;
  - un non-membre reçoit **404** sur toutes les routes du projet ;
  - un membre au rôle insuffisant reçoit **403** (« Droit insuffisant : rôle « X » au minimum requis. »).
- **Rôles** (ordonnés) : viewer (Lecteur) < editor (Éditeur) < key_manager (Gestionnaire des machines) < owner (Propriétaire).

  | Action | Rôle minimal |
  |---|---|
  | read (projet, runs, membres, épingles, activité) | viewer |
  | comment | viewer |
  | run | editor |
  | pin (épingler et désépingler) | editor |
  | machines (liste, ajout, suppression) | key_manager |
  | edit_project | owner |
  | invite (création, liste, révocation des invitations) | owner |
  | manage_members (rôle, titre, retrait) | owner |
  | delete_project | owner |

  - Le **dernier propriétaire** ne peut être ni rétrogradé ni retiré (409).
  - Le **titre** (CEO, CTO…) est une étiquette sans effet sur les droits.
  - La matrice est servie par `GET /roles`.
- **Invitations** :
  - lien valable **7 jours**, construit à partir de `CORS_ORIGIN` + `/invitations/<token>` ;
  - **aucun e-mail envoyé** ;
  - statuts : pending, accepted, revoked, expired (expiration détectée à la lecture) ;
  - pour accepter, il faut être connecté avec le **même e-mail** (403 sinon), avec 410 si l'invitation a expiré et 409 si elle n'est plus valable ou si l'utilisateur est déjà membre ;
  - doublon refusé (409) : invitation déjà en attente, ou personne déjà membre ;
  - `GET /invitations/{token}` est public, pour la page d'acceptation.
- **Runs** :
  - kinds `diagnostic`, `compare`, `scaling` et `hardware` ;
  - `POST` répond **202** avec le run en `pending` ;
  - statuts pending → running → done ou failed ;
  - limites validées :

    | Paramètre | Bornes |
    |---|---|
    | qubits | 2 à 8 |
    | couches | 1 à 8 |
    | échantillons | 50 à 5000 |
    | n_seeds | 1 à 10 |
    | seed | 0 à 1 000 000 |
    | runs en cours par utilisateur | 2 au plus (**429** au-delà) |
    | durée d'un run | **10 minutes** au plus, puis échec propre (processus tué) |

  - au plus **2 calculs** simultanés au total ;
  - au démarrage, les runs restés pending ou running passent en failed, avec le message « Interrompu : l'API a redémarré avant la fin du calcul. » ;
  - liste filtrable (status, kind) et paginée (limit, offset), sans les résultats.
- **Résultats par kind** :

  | kind | Résultat |
  |---|---|
  | diagnostic | expressibility, entangling_capability, gradient {mean_variance, active_mean_variance, inactive_fraction, n_inactive_parameters, n_parameters}, stats, histogram |
  | compare | `{"rows": [...compare + "ansatz" + "pareto" (bool, calculé sur expressibilité / variance active)]}` |
  | scaling | `{"series": [{ansatz, observable, rows, fit_active, fit_all}]}` ; `compare_observables=True` calcule Z0 et Zall |
  | hardware | dict de `hardware_cost` |

  Les `NaN` deviennent `null`.
- **Collaboration** :
  - commentaires sur un run (1 à 2000 caractères, espaces retirés aux extrémités) ;
  - circuits épinglés (unicité ansatz + qubits + couches, 409 en cas de doublon) ;
  - machines « fournisseur + libellé ». Les champs `secret`, `api_key`, `token`, `key` et `password` sont refusés (422, « Ce prototype ne stocke aucune clé ni aucun secret de machine… »).
- **Fil d'activité** (paginé, du plus récent au plus ancien), avec les événements run_launched, run_done, run_failed, comment_added, circuit_pinned, member_invited, member_joined, role_changed et machine_added.
- **Catalogue public** : `GET /ansatz` (nom, nom d'affichage, description, formule des paramètres), `GET /ansatz/{name}/structure?n_qubits=&layers=` (structure + `stats` = circuit_stats), `GET /topologies` (libellés : Ligne, Anneau, Complète, Hexagone lourd (19 qubits)), `GET /health`.

La liste complète des routes est dans `docs/API.md`, la matrice des droits dans `docs/ROLES.md`.

---

## 6. Application web (`web/`) : écrans

**Barre latérale** :
- logo ;
- « Tous les projets » ;
- puis, dans un projet : nom du projet, Projet, Diagnostic, Comparateur, Ansatz, Plateau stérile, Jobs et matériel, Équipe ;
- en bas : nom de l'utilisateur et « Se déconnecter ».

Sous 800 px de large, elle passe en bandeau horizontal.

**Règles générales** :
- chaque écran a ses états de chargement, d'erreur (avec « Réessayer ») et de vide ;
- une action interdite par le rôle est **désactivée avec une infobulle et une description accessible** (« Réservé au rôle « Éditeur » ou supérieur. »), **jamais masquée** ;
- toute réponse 401 efface la session et renvoie vers `/login?next=...`.

| Route | Écran | Contenu |
|---|---|---|
| `/login` | Connexion | e-mail, mot de passe ; suit `next` (chemins internes seulement, pas de redirection ouverte) |
| `/register` | Inscription | nom, e-mail, mot de passe (≥ 10), confirmation ; validation avant tout appel à l'API |
| `/invitations/:token` | Invitation | projet, rôle, e-mail, date d'expiration ; boutons Se connecter / Créer un compte, ou « Accepter l'invitation » ; message si l'e-mail ne correspond pas ou si l'invitation est expirée ou révoquée |
| `/projects` | Projets | création (nom, description) ; tableau des projets avec le rôle |
| `/projects/:id` | Projet | onglets Activité (« Afficher plus »), Circuits épinglés (désépingler), Runs (pastilles d'état, lien vers le détail), Membres |
| `.../equipe` | Équipe | tableau des membres (rôle et titre modifiables par le propriétaire, « Retirer ») ; invitation avec lien copiable ; invitations en attente avec révocation (les autres rôles voient une explication) ; matrice « Ce que chaque rôle permet » (Oui/Non) lue depuis `/roles` |
| `.../diagnostic` | Diagnostic | voir ci-dessous |
| `.../comparateur` | Comparateur | voir ci-dessous |
| `.../ansatz` | Ansatz | tableau des 7 ansatz (choix par bouton) ; qubits et couches ; schéma SVG (boîtes violettes RX/RY/RZ au texte blanc, CNOT en point de contrôle et disque encre avec « + » blanc, fils horizontaux, défilement horizontal) ; tableau des caractéristiques (paramètres, profondeur, portes à 2 qubits, comptes par type) |
| `.../plateau-sterile` | Plateau stérile | voir ci-dessous |
| `.../jobs` | Jobs et matériel | voir ci-dessous |
| `.../jobs/:runId` | Détail d'un run | paramètres, état, dates, lien vers l'écran du résultat, erreur, JSON brut repliable, commentaires |

**Diagnostic** :
- formulaire : ansatz, qubits, couches, échantillons (défaut 1000), graine, observable (Locale Z0 / Globale Z⊗n) ;
- validation des bornes en direct, avec bouton désactivé ;
- avertissement sous 1000 échantillons ;
- « Diagnostiquer » lance le run ; son identifiant est placé dans l'URL `?run=ID`, puis l'écran interroge l'API toutes les 2 s ;
- résultat : 3 cartes avec bouton d'aide « ? », dont « Variance du gradient » avec actifs et inactifs, puis l'histogramme des fidélités (barres violettes, courbe de Haar en corail) ;
- boutons « Télécharger en CSV » et « Épingler ce circuit » ;
- commentaires.

**Comparateur** :
- cases à cocher pour les ansatz, puis qubits, couches, échantillons, nombre de graines (1 à 10) et graine ;
- tableau « moyenne ± écart-type » ;
- ligne de rappel des paramètres et phrase de lecture ;
- nuage expressibilité / variance active, avec le front de Pareto en violet plein et les autres points en violet clair cerclé de violet, plus des barres d'erreur avec plusieurs graines ;
- phrase de Pareto et note, CSV, commentaires.

**Plateau stérile** :
- ansatz (4 au plus), qubits min et max, mode (Fixe / Proportionnel aux qubits) ;
- curseur Couches **désactivé en mode proportionnel**, avec la note ;
- échantillons (défaut 100), graine ;
- observable, ou case « Comparer local et global » qui désactive l'observable ;
- information « calcul plus long » au-delà de 6 qubits ;
- courbes en échelle logarithmique : actifs en trait plein, tous les paramètres en pointillé ; en comparaison, local en trait plein et global en trait mixte. Une couleur et un marqueur par ansatz (violet rond, encre carré, corail triangle, gris losange) ;
- tableau des facteurs et des R², ligne « Couches : … », phrases, note sur l'observable, CSV, commentaires.

**Jobs et matériel** :
- onglet Runs : liste avec filtres état et type, pastilles d'état, « Afficher plus » ;
- onglet Matériel : formulaire (ansatz, qubits, couches, topologie, graine du transpileur) ; tableau des 3 niveaux (Circuit d'origine / Après traduction / Après routage) ; « Surcoût du routage ×… » ; CSV ;
- section Machines : « Simulateur local … Disponible » ; liste et ajout pour le key_manager et au-delà ; mention « Aucune clé n'est stockée dans ce prototype ».

**Export CSV (côté client)** : UTF-8, virgule séparatrice, point décimal, noms de colonnes techniques, première ligne `# clé=valeur; …; version=0.2.0`.

**Session** : jeton en mémoire et dans `sessionStorage`, sous la clé `stochastiq.token`. C'est un compromis : la session survit au rechargement de l'onglet, mais un script injecté (XSS) pourrait la lire. Il est documenté dans `web/README.md`.

---

## 7. Dashboard Streamlit (outil local)

- **Lancement** : `streamlit run dashboard/app.py`.
- **Cinq onglets** :
  - Diagnostic : 3 cartes et histogramme ;
  - Comparateur : tableau, phrase, nuage de Pareto, barres d'expressibilité ;
  - Ansatz : schéma Qiskit en mpl au style StochastiQ, caractéristiques ;
  - Matériel : 3 niveaux, surcoût du routage, phrase ;
  - Plateau stérile : observable, comparaison local/global, deux séries, tableau, phrases.
- Chaque tableau s'exporte en CSV, et les calculs sont mis en cache.
- C'est la **référence** des règles de lecture reprises dans le web.

---

## 8. Déploiement, démo, documentation

- **Docker** : `docker compose up --build`.
  - Service `api` : image `python:3.12-slim`, utilisateur non root, base dans le volume `api-data` (`/data/stochastiq.db`), healthcheck `/health`, port 8000.
  - Service `web` : build Vite, servi par nginx avec repli pour l'application monopage, sur le port **5173** de l'hôte.
  - `.env` est facultatif (variables ENV, SECRET_KEY, DATABASE_URL, CORS_ORIGIN, voir `.env.example`).
- **Démo** : `scripts/seed_demo.py` crée :
  - 4 comptes fictifs, mot de passe **`demo-stochastiq-2026`** :

    | Compte | E-mail | Rôle | Titre |
    |---|---|---|---|
    | [Membre 1] | membre1@example.test | owner | CEO |
    | [Membre 2] | membre2@example.test | key_manager | CTO |
    | [Membre 3] | membre3@example.test | editor | Chercheur |
    | [Membre 4] | membre4@example.test | viewer | Stagiaire |

  - le projet « Démo universitaire », 4 runs réels, 3 commentaires, 2 épingles et une machine sans clé.

  Le script est idempotent : il refuse de s'exécuter si les comptes existent déjà.
- **Lancer en local** (PowerShell, depuis la racine) :
  - `cd api; ..\.venv\Scripts\uvicorn stochastiq_api.main:app --reload --port 8000` ;
  - `cd web; npm run dev` ;
  - démo : `.venv\Scripts\python scripts\seed_demo.py --database-url sqlite:///./api/stochastiq.db`. Le script doit viser la base de l'API (`api/stochastiq.db`), sinon les comptes n'existent pas pour l'API.
- **Documentation** :
  - `README.md` (racine) ;
  - `api/README.md`, `web/README.md`, `dashboard/README.md` ;
  - `docs/ARCHITECTURE.md` (schéma mermaid), `docs/ROLES.md`, `docs/API.md`, `docs/METRIQUES.md` ;
  - `CHANGELOG.md` (0.1.0 et 0.2.0) ;
  - `examples/demo.ipynb` : notebook avec compare, Pareto, scaling et hardware_cost, sorties gardées, 104 Ko.

---

## 9. Tests (état vert sur `release/v0.2` ; état v0.3 en section 12.11)

| Suite | Commande | Résultat |
|---|---|---|
| Bibliothèque (+ dashboard, + PennyLane si installé) | `pytest` (racine) | 239 tests |
| API | `cd api; pytest` | 171 tests |
| Front | `cd web; npm test` | 51 tests |
| Build front | `cd web; npm run build` | réussi |
| Bout en bout | `cd web; npx playwright test` | 1 parcours (inscription, projet, diagnostic, invitation d'un lecteur, rendu à 390 px), réussi 4 fois sur 5 |
| Docker | `docker compose config`, `up` | valide et démarré pour de vrai |

La CI (`.github/workflows/tests.yml`) a trois jobs :
- bibliothèque sur Python 3.10, 3.11 et 3.12 ;
- API sur 3.12 ;
- front (npm test et build).

Elle **n'a jamais tourné**, puisque rien n'a été poussé.

---

## 10. État Git (v0.2 ; état v0.3 en section 12.12)

- **Branche courante** : `release/v0.2`. La copie de travail est propre, à l'exception de ces deux rapports, non commités.
- **Tags locaux** :
  - `v0.1.0` → `release/v0.1` (bibliothèque complète) ;
  - `v0.2.0` → `release/v0.2` (`b0c3b9f`, tout).
- **`main`** : `7d14e11` (« Première version : expressibility() »), jamais modifiée depuis.
- **Branches, dans l'ordre chronologique** :
  - feature/metrics-et-ansatz, feature/dashboard, fix/dashboard-lecture, feature/vrais-ansatz, fix/gradient-variance, feature/graphiques-diagnostic, fix/plateau-sterile-ui, feature/prototype-final ;
  - `release/v0.1` (les fusionne toutes, avec feature/observable-globale et feature/m0-bibliotheque) ;
  - feature/m1-api-comptes, feature/m2-runs, feature/m3-web-socle, feature/m4-ecrans-scientifiques, feature/m5-deploiement ;
  - `release/v0.2`.

  Chaque branche part de la précédente : l'historique est linéaire et les fusions se font sans conflit.

---

## 11. Points ouverts, limites et dérogations connues

- **LICENSE** : le titulaire vaut toujours `[NOM]`, faute de le connaître.
- **Test de bout en bout** : un échec intermittent unique, juste après un `npm run build`, puis 4 réussites. Cause non identifiée ; hypothèse non vérifiée : rechargement de Vite à froid.
- **Python 3.10** : non installé sur la machine, donc la CI en 3.10 n'est pas vérifiée (la 3.11 l'a été localement).
- **Qiskit** : `pyproject.toml` déclare `qiskit>=1.0`, mais les tests utilisent `real_amplitudes` (Qiskit ≥ 1.3). Le plancher n'a pas été relevé.
- **Machines** : lire leur liste demande le rôle key_manager (matrice de la consigne). Les autres rôles voient une explication.
- **Runs** :
  - un exécuteur `ProcessPoolExecutor` à 1 worker **par run** (2 au plus en même temps), pour pouvoir tuer un run trop long. Sous Python 3.12, cela passe par l'attribut privé `_processes` ;
  - au démarrage, les runs `pending` sont aussi marqués en échec, pas seulement les `running`.
- **Rendu visuel** : il n'a été vérifié qu'à travers 7 captures Playwright dans Chromium. Pas de Firefox ni de Safari, pas d'audit d'accessibilité automatique (axe) ni de test avec un lecteur d'écran.
- **Notebook** : le notebook `examples/demo.ipynb` a été réécrit. Une ancienne modification locale de l'auteur est sauvegardée hors dépôt, dans le scratchpad de la session précédente.
- **Limites du prototype**, documentées dans le README :
  - invitations sans e-mail ;
  - aucune clé de machine ;
  - SQLite, sans file de jobs externe ;
  - pas de réinitialisation de mot de passe ;
  - pas d'audit de sécurité.
- **Feuille de route** (README) :
  - file de jobs externe ;
  - PostgreSQL ;
  - réinitialisation de mot de passe et e-mails ;
  - cookie HttpOnly avec protection CSRF ;
  - audit de sécurité ;
  - comparaison avec le code d'origine de QCBM Lab ;
  - modèles de bruit.

---

## 12. Version 0.3.0 : le client apporte son problème et ses ansatz

Mission v0.3 (plan et notes : `docs/PLAN_V0.3.md`). Un client apporte sa distribution de probabilités (le « problème ») et ses propres ansatz, les diagnostique, les entraîne en simulation avec ou sans bruit, les compare à des méthodes classiques simples, et obtient une prédiction et une recommandation d'une IA entraînée sur une base de résultats qui s'enrichit à chaque run.

### 12.1 Jalons et branches

| Jalon | Branche | Contenu |
|---|---|---|
| 0 | `feature/m6-corrections` | message de durée maximale construit à partir de `RUN_TIMEOUT_SECONDS` (« 0,5 seconde », « 10 minutes ») ; Qiskit ≥ 1.3 |
| 1 | `feature/m7-problemes` | distributions, problèmes, import CSV, écran Problèmes |
| 2 | `feature/m8-ansatz-client` | ansatz personnalisés (spec, OpenQASM 3), écran Mes ansatz |
| 3 | `feature/m9-entrainement` | entraînement QCBM, références classiques, écran Entraînement |
| 4 | `feature/m10-bruit` | bruit simulé (qiskit-aer), évaluation sous bruit, carte « Dégradation sous bruit » |
| 5 | `feature/m11-base-resultats` | base de résultats, partage avec l'IA, grille de référence |
| 6 | `feature/m12-prediction` | IA de prédiction, route `/predict`, `docs/PREDICTION.md` |
| 7 | `feature/m13-recommandation` | recommandation, rapport imprimable, parcours Playwright |
| 8 | `feature/m14-release` | modèle entraîné au démarrage, démo enrichie, versions, documentation, Docker, tag |
| 9 | (non commencé) | collecte IBM, facultative : **ne pas commencer sans accord explicite de l'auteur** |

Chaque branche part de la précédente et est fusionnée en `--no-ff` dans `release/v0.3` (créée depuis `release/v0.2`), les quatre suites vertes.

### 12.2 Dérogations validées par l'auteur

- **Périmètre** : l'entraînement de QCBM en simulation et le bruit simulé entrent dans le périmètre.
- **Dashboard Streamlit** : il n'est pas étendu ; les phrases de lecture des nouvelles fonctions n'existent que dans le web.
- **Critère de l'IA** (jalon 6) : séparé entre valeur centrale (gain ≥ 20 % sur la meilleure référence) et intervalle (CQR, affiché seulement si la couverture mesurée pour un cas comparable est entre 70 et 90 %). Les deux versions sont dans `docs/PREDICTION.md`.

### 12.3 Problèmes (distributions cibles)

- Distributions de référence : gaussienne, bimodale, log-normale, uniforme, Bars-and-Stripes (4 et 6 qubits seulement), Boltzmann d'Ising (graine). De 2 à 8 qubits.
- Import CSV (1 Mo et 100 000 lignes au plus ; le texte n'est pas conservé) :
  - format « probabilités » : `chaîne de bits,probabilité`, qubit n−1 à gauche, somme égale à 1 à 1e-6 près ;
  - format « échantillons » : une ou plusieurs variables continues, un intervalle par variable, encodage binaire ou de Gray.
- Caractéristiques affichées : qubits, entropie normalisée, part du support non nul, probabilité maximale, information mutuelle moyenne entre bits.
- Droit `problems` (éditeur) ; événement d'activité `problem_added`.

### 12.4 Ansatz personnalisés

- **Spec** : 1 à 3 rotations parmi RX, RY, RZ, et un motif d'intrication (anneau, anneau simple, fort, ligne, toutes les paires, briques, aucun) ou une liste de CNOT « contrôle-cible » (64 au plus ; le plus grand indice fixe le nombre de qubits).
- **OpenQASM 3** (20 000 caractères au plus) : paramètres déclarés par `input float[64] nom;`, chacun utilisé par une seule porte RX, RY ou RZ ; portes fixes autorisées seulement. OpenQASM 2 n'a pas de paramètres libres.
- Validation : 2 à 8 qubits, 1 à 300 paramètres, profondeur ≤ 500 ; message qui nomme la porte fautive. **Aucun code Python client n'est jamais exécuté.**
- Les runs acceptent `{"custom_id": n}` ; l'API le remplace par le contenu complet. Un ansatz à nombre de qubits fixé est refusé pour le scaling et pour un problème d'une autre taille. Seuls les ansatz du catalogue peuvent être épinglés.
- Droit `custom_ansatz` (éditeur).

### 12.5 Entraînement

- Écran Entraînement : problème, ansatz, couches, perte (KL, MMD, TVD), optimiseur (Adam, SPSA, COBYLA ; Adam interdit avec la TVD), itérations (10 à 1000), pas (0 < pas ≤ 5), probabilités exactes ou tirages (100 à 100 000), graine.
- Résultat : tableau « Quantique contre classique » (KL, TVD, Hellinger, paramètres) avec les deux références (marginales indépendantes, arbre de Chow-Liu), courbe de perte en échelle logarithmique, distribution apprise contre cible, deux exports CSV, commentaires.
- Phrase de lecture : TVD atteinte, comparaison avec la meilleure référence par la règle des 10 % (« fait mieux » sous 0,9 ×, la référence « fait mieux » au-delà de 1,1 ×, sinon « Équivalent à la meilleure référence classique (écart inférieur à 10 %) »), portée (« Une seule initialisation… »).
- Évaluation facultative sous bruit (profil, topologie) : ligne supplémentaire et phrase « Avec les mêmes paramètres appris, sous le bruit « fort » (topologie ligne), la TVD passe de … à …. Les profils de bruit sont des ordres de grandeur, pas des calibrations de machines réelles. »

### 12.6 Bruit simulé

- Profils faible, moyen, fort (dépolarisation 1 et 2 qubits, erreur de lecture : 1e-4/1e-3/1e-2, 5e-4/5e-3/2e-2, 1e-3/1e-2/5e-2) ou personnalisé (taux de 0 à 0,5). Ordres de grandeur, pas des calibrations.
- Topologies ligne, anneau, complète ; heavy-hex refusé (matrice densité trop grande).
- Run `noise` (TVD moyenne idéal / bruité sur des paramètres aléatoires) ; diagnostic avec `noise_profile` : carte « Dégradation sous bruit » (20 jeux de paramètres, ligne).

### 12.7 Base de résultats et partage

- Chaque run réussi de diagnostic, de bruit ou d'entraînement ajoute des lignes (`diagnostic`, `noise`, `training`, `training_noise`) : empreinte de l'ansatz, qubits, couches, caractéristiques du circuit et du problème, famille du problème, profil de bruit, grandeurs mesurées, version de la bibliothèque. **Jamais de probabilités brutes.**
- Case « Partager les résultats de ce projet avec l'IA » sur la page du projet : désactivée par défaut, propriétaire seulement. L'IA n'apprend que sur la grille de référence et les projets qui partagent.
- Grille de référence (`scripts/build_results.py`) : 756 configurations, 3024 lignes, 0,1 h avec 8 processus ; export `data/results_grid.csv`.

### 12.8 Prédiction

- `POST /projects/{id}/predict` : TVD finale prédite et, avec un profil, dégradation et TVD sous bruit, chacune avec l'intervalle 10-90 % ou « Intervalle non fiable pour ce cas : couverture mesurée X %. ».
- Validation qui correspond au cas : ansatz inconnu, famille inconnue (un problème CSV est de famille « csv », jamais vue par la grille), qubits hors de 2 à 6 ; la plus défavorable s'il y en a plusieurs ; sinon découpage aléatoire.
- Résultats réels (après CQR) : intervalles affichés pour un ansatz du catalogue sur une distribution de référence (79,0 % et 79,5 % de couverture) et, pour la TVD finale seulement, pour un ansatz personnalisé (74,6 %). Pas d'intervalle pour les problèmes CSV ni à 7 et 8 qubits. Détail : `docs/PREDICTION.md`.
- Sans modèle : 409 « Aucun modèle entraîné : lancez scripts/train_predictor.py. ». Le conteneur de l'API et `seed_demo.py` l'entraînent s'il est absent de `MODELS_DIR`.

### 12.9 Recommandation et rapport

- Écran Recommandation : problème, 2 à 7 ansatz (cases à cocher), couches, bruit facultatif, topologie, budget d'itérations (200 à 7000 ; budget // 200 entraînements conseillés au plus).
- Pour chaque ansatz : diagnostic léger, TVD prédite (ou mesurée si un entraînement réussi existe dans le projet pour le même problème et le même nombre de couches ; il prime), intervalle ou motif de son absence, source.
- Verdict (règles dans l'API, phrases dans le web), selon la nature de la preuve de l'ansatz classé premier (dérogation validée par l'auteur au jalon 8) :
  - valeur mesurée, règle des 10 % : « Le quantique se justifie sur ce problème : « A » atteint une TVD mesurée de …, plus de 10 % sous la meilleure TVD classique (… ; P paramètres pour l'ansatz, Q pour la référence). », la phrase symétrique « ne se justifie pas », ou « Équivalent au classique (écart inférieur à 10 %) : le quantique n'apporte rien sur ce problème. … » (jamais de « borne » pour une mesure) ;
  - valeur prédite avec intervalle fiable : « Le quantique se justifie sur ce problème : la borne haute de « A » (TVD …) est sous la meilleure TVD classique (…). », la phrase symétrique avec la borne basse, sinon « Indéterminé : entraînez « A » et « B » pour trancher. » ;
  - valeur prédite sans intervalle : marge de 2 × l'erreur moyenne de validation (pour une TVD mesurée combinée à une dégradation prédite : 0,1 × meilleure TVD classique + 2 × erreur moyenne de la dégradation ; si la dégradation a un intervalle fiable, celui-ci est élargi de 0,1 × meilleure TVD classique de chaque côté), « Le quantique se justifie probablement… » ou « ne se justifie probablement pas… », sinon « Indéterminé » ;
  - « « A » et « B » sont indistinguables : leurs intervalles se recouvrent. » quand leurs intervalles effectifs se recoupent.
  - Cas réel qui a motivé la règle : 0,0585 mesuré contre 0,0588 (Chow-Liu) donnait « se justifie » ; c'est désormais « Équivalent ».
- Page Rapport (`/projects/{id}/rapport?run=`) : cadre, verdict, classement, méthode et limites ; Imprimer (navigation et boutons masqués par `@media print`), CSV, JSON.

### 12.10 Navigation

Projet, Problèmes, Diagnostic, Comparateur, Ansatz, Mes ansatz, Entraînement, Recommandation, Plateau stérile, Jobs et matériel, Équipe. La page Rapport s'ouvre depuis la Recommandation.

### 12.11 Tests (état vert sur `feature/m14-release`, avant la fusion finale)

| Suite | Commande | Résultat |
|---|---|---|
| Bibliothèque | `pytest` (racine) | 359 tests |
| API | `cd api; pytest` | 288 tests sous Windows ; 286 tests sous Linux (conteneur `python:3.12-slim`, une fois) |
| Front | `cd web; npm test` | 81 tests |
| Build front | `cd web; npm run build` | réussi |
| Bout en bout | `cd web; npx playwright test` | 2 parcours ; 3 réussites sur 3 chacun au jalon 7, puis réussis au jalon 8 |
| Docker | `docker compose up --build` | démarré pour de vrai sur un volume neuf : modèle entraîné en 103 s, démo (6 runs) réussie, `/predict` en 200, modèle réutilisé au redémarrage |

Suites validées sous Windows ; API validée une fois sous Linux (conteneur) ; bibliothèque et front non testés sous Linux.

### 12.12 État Git

Voir le rapport final de la mission v0.3 (dans la conversation) et `git log --oneline --graph release/v0.3`. Tag local `v0.3.0` sur `release/v0.3` ; rien n'a été poussé ; `main` n'a pas été modifiée.

### 12.13 Points ouverts et limites (v0.3)

- **Blocage inexpliqué** (jalon 5) : la suite de l'API s'est une fois bloquée environ 45 minutes sous Windows ; la relance avec `faulthandler_timeout=300` est passée. Le minuteur contourne le problème, il ne le corrige pas.
- **Blocage expliqué et corrigé** (jalon 8) : sous Linux, `fork` bloquait un routage Qiskit dans un processus de calcul après une transpilation dans le processus de l'API ; processus créés par `spawn` partout depuis.
- **Références classiques simples** : marginales indépendantes et arbre de Chow-Liu ; un verdict « le quantique se justifie » ne vaut que face à elles.
- **IA** : intervalles absents pour les problèmes CSV et à 7 et 8 qubits ; une seule graine par configuration de la grille.
- **Bruit** : profils d'ordre de grandeur, pas des calibrations ; rz sans erreur.
- **Rendu** : vérifié par captures Playwright dans Chromium seulement ; impression réelle (PDF, papier) et contenu de l'export JSON non vérifiés.

### Corrections prévues en v0.3.1 (non codées)

- **Affichage de la recommandation** : étiqueter les deux messages de couverture (TVD finale et dégradation) ; remplacer « leurs intervalles se recouvrent » par « aucun intervalle fiable : impossible de les départager » quand aucun ansatz n'a d'intervalle ; citer toutes les couvertures dans la partie Méthode du rapport.
- **Priorité haute** : décider si une famille est connue par une distance dans l'espace des `problem_features`. Un Bars-and-Stripes importé en CSV est aujourd'hui classé « famille inconnue », donc sans intervalle.
- **Référence classique plus forte** : mélange de lois, ou petite machine de Boltzmann. Les références actuelles (marginales indépendantes, arbre de Chow-Liu) sont **simples** : battre l'arbre de Chow-Liu ne prouve pas un avantage sur les méthodes classiques en général.
- **Ansatz sans intrication** : calculer leur valeur directement (meilleure distribution produit, comme la référence « marginales indépendantes ») plutôt que la prédire. Aujourd'hui, la borne basse prédite de RotationOnly peut descendre à 0,25 alors que la théorie interdit de descendre sous environ 0,37 sur le cas observé.
- **Grille** : entraîner chaque configuration avec plusieurs graines, pour limiter l'effet des minima locaux.

