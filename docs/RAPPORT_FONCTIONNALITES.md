# Rapport 1 : fonctionnalités de StochastiQ (état au 6 novembre 2026, version 0.2.0)

Ce rapport décrit **ce que fait** le projet, écran par écran et fonction par fonction, ainsi que les règles métier, les conventions imposées par l'auteur et l'état du dépôt. Le rapport 2 (`docs/RAPPORT_CODE.md`) explique **comment** c'est codé. Les deux ensemble suffisent pour reprendre le travail sans autre contexte.

---

## 1. Le projet en bref

- **Objet** : StochastiQ est un prototype universitaire de diagnostic d'ansatz (circuits quantiques paramétrés) pour les machines de Born quantiques (QCBM), construit sur Qiskit. Il mesure, pour un circuit :
  - l'expressibilité ;
  - la capacité d'intrication ;
  - la variance du gradient (détection des plateaux stériles) ;
  - le coût de transpilation sur des topologies matérielles.
- **Dépôt** : `C:\Users\ldvcb\Desktop\Sto\StochastiQ_Lib`, remote `https://github.com/Ldvccc/StochastiQ_Lib`. Rien n'a jamais été poussé depuis le début du travail.
- **Contexte** : prototype universitaire, **pas une application de production**. Cette mention figure dans le README et doit y rester.
- **Quatre parties** :
  1. **Bibliothèque Python** `stochastiq` (`src/stochastiq/`, version 0.1.0) : tous les calculs, **aucune dépendance web**.
  2. **API FastAPI** (`api/`, paquet `stochastiq_api`, version 0.2.0) : comptes, projets, rôles, invitations, runs, activité.
  3. **Application web React** (`web/`, version 0.2.0) : écrans d'équipe et écrans scientifiques.
  4. **Dashboard Streamlit** (`dashboard/`) : outil local d'exploration, **hors application web**.
- **Sens des dépendances** : l'API importe la bibliothèque, **jamais l'inverse**. Le front ne parle qu'à l'API.

---

## 2. Conventions imposées par l'auteur (à respecter dans toute suite)

- **Langue** : interface, messages d'erreur, docstrings, commentaires et messages de commit en **français**.
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
  - les branches de release (`release/v0.1`, `release/v0.2`) regroupent le travail par fusions `--no-ff` ; les tags sont locaux (`v0.1.0`, `v0.2.0`).
- **Méthode** :
  - lire le code existant avant de modifier ;
  - ne coder que ce qui est demandé ;
  - signaler toute dérogation ;
  - ne jamais corriger « au hasard » un écart inexpliqué : le montrer ;
  - si un jalon échoue après deux tentatives de correction, s'arrêter, décrire le blocage et proposer une solution.
- **Rapports de fin de tâche** : tests lancés avec leur résultat affiché, liste de ce qui n'a pas pu être vérifié (en particulier le rendu visuel), liste des dérogations.
- **Hors périmètre (ne pas coder)** :
  - entraînement de QCBM ;
  - connexion à de vraies machines (IBM, Origin) ;
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

## 9. Tests (état vert sur `release/v0.2`)

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

## 10. État Git

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
