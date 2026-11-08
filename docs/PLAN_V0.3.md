# Plan v0.3 : de la présélection à l'apprentissage

Ce document décrit ma lecture de la mission v0.3, jalon par jalon, avec les fichiers touchés et les risques. Il part de l'état v0.2.0 décrit par `docs/RAPPORT_FONCTIONNALITES.md` et `docs/RAPPORT_CODE.md`, dont les conventions s'appliquent. Seules exceptions : les dérogations du §2 de la mission (entraînement et bruit simulé entrent dans le périmètre ; les phrases de lecture des nouvelles fonctions n'existent que dans le web).

## Lecture d'ensemble

- **Objectif** : un client apporte sa distribution et ses ansatz, puis les diagnostique, les entraîne en simulation (avec ou sans bruit) et les compare à des références classiques. Il obtient enfin une prédiction et une recommandation, produites par un modèle appris sur une base de résultats qui grossit à chaque exécution.
- **Frontière d'architecture** :
  - calcul générique dans la bibliothèque `stochastiq` (`distributions`, `custom_ansatz`, `training`, `baselines`, `noise`), sans dépendance web ;
  - tout ce qui accumule ou exploite des données dans l'API (`api/stochastiq_api/ml/` : base de résultats, prédiction, recommandation).
- **Git** :
  - `release/v0.3` est créée depuis `release/v0.2` ;
  - chaque branche `feature/m6…m14` part de la précédente ;
  - fusion `--no-ff` dans `release/v0.3` à la fin de chaque jalon, avec les 4 suites vertes (bibliothèque, API, front, build) ;
  - Playwright aux jalons 7 et 9 ;
  - tag local `v0.3.0` à la fin du jalon 8 ;
  - jamais de push, `main` intacte.
- **Sécurité** : aucun code Python client n'est exécuté. Les ansatz clients sont soit une spec JSON validée par pydantic, soit du QASM analysé par le parseur de Qiskit puis validé (portes, taille). Toutes les entrées sont bornées.
- **Versions** : API et web 0.3.0, bibliothèque 0.2.0 (jalon 8).

## Jalon 0 : corrections héritées (`feature/m6-corrections`)

- **Constat** : le message de dépassement de durée est déjà calculé à partir de `run_timeout_seconds` (`jobs.py`). Il a deux défauts : un point décimal (« 0.5 secondes ») et un accord faux (« 1 minutes »). Correction : formatage français et accord, avec un test exact à 0,5 s (« Durée maximale dépassée (0,5 seconde). »).
- **Plancher Qiskit** : les tests utilisent `qiskit.circuit.library.real_amplitudes`, une fonction apparue dans Qiskit 1.3. Je relève donc `qiskit>=1.3` dans `pyproject.toml`, après vérification de son absence dans 1.2.
- **Fichiers** : `api/stochastiq_api/jobs.py`, `api/tests/test_runs.py`, `pyproject.toml`.
- **Commit de documentation à part** : ce plan et les deux rapports v0.2, restés non commités jusqu'ici.

## Jalon 1 : problèmes du client (`feature/m7-problemes`)

- **Bibliothèque**, nouveau module `src/stochastiq/distributions.py` :
  - références `gaussian`, `bimodal`, `lognormal`, `uniform`, `bars_and_stripes` (n = 4 ou 6) et `ising_boltzmann` (couplages aléatoires, `seed`) ; vecteurs de 2^n probabilités, n de 2 à 8 ;
  - `from_samples(samples, n_qubits, ranges, encoding="binary"|"gray")` : n/d qubits par variable, `ValueError` si n n'est pas divisible par d ;
  - `from_probabilities(mapping)` : refuse une probabilité négative et une somme qui s'écarte de 1 de plus de 1e-6 ;
  - `problem_features(probs)` : n, entropie normalisée, part du support, probabilité maximale, information mutuelle moyenne entre paires de bits ;
  - convention little-endian de Qiskit (l'indice i a le qubit q au bit q), documentée et testée.
- **API** :
  - modèle `Problem` et migration 0003 ;
  - routes CRUD `/projects/{id}/problems`, plus un import CSV en deux formats (au plus 1 Mo et 100 000 lignes) ;
  - actions `problems_read` (viewer) et `problems_write` (editor) dans `PERMISSIONS` et dans `web/src/lib/roles.ts` ;
  - événement `problem_added`.
- **Web** : écran « Problèmes » (liste, création depuis une référence ou un CSV, histogramme de la distribution).
- **Risque** : le parsing CSV. Il passe par le module `csv` de la bibliothèque standard, avec des bornes strictes : jamais de pandas sur une entrée client brute.

## Jalon 2 : ansatz du client (`feature/m8-ansatz-client`)

- **Bibliothèque**, nouveau module `custom_ansatz.py` :
  - spec JSON et `build_from_spec` (entangleurs de `ansatz.py` rendus publics sous un nom stable, les fonctions privées restant des alias, sans changement de comportement) ;
  - `load_qasm(text)` : OpenQASM 2 via `qiskit.qasm2` ; OpenQASM 3 via `qiskit.qasm3`, qui demande le paquet `qiskit-qasm3-import`, ajouté en option `qasm3` et signalé ;
  - `validate_ansatz(qc)` : au plus 8 qubits, 300 paramètres, portes RX, RY ou RZ d'angle égal à un paramètre seul, profondeur bornée (je propose 500, à confirmer à la mesure) ;
  - `circuit_structure(qc)` ;
  - `gradient_scaling` accepte un constructeur.
- **API** : modèle `CustomAnsatz`, migration 0004, CRUD avec validation ; les runs acceptent `ansatz = nom` ou `{"custom_id": n}`, résolus en spec ou en QASM complet dans les paramètres du run.
- **Web** : écran « Mes ansatz » ; les formulaires existants proposent aussi les ansatz du projet.
- **Risques** :
  - les paramètres d'un QASM sont nommés librement ; `assign_parameters` suit l'ordre trié de Qiskit, et je le documente ;
  - le simulateur en lot exige un `Parameter` seul par porte, ce qui est vérifié par `validate_ansatz`.

## Jalon 3 : entraînement QCBM (`feature/m9-entrainement`)

- **Bibliothèque** :
  - refactoriser `_expectations` en `batched_probabilities` (vecteur de probabilités par jeu de paramètres) et réécrire les valeurs moyennes par-dessus, sans changer aucun résultat : les tests de concordance restent tels quels ;
  - `training.py` : `train_qcbm` avec les pertes KL, TVD et MMD (noyau gaussien), les optimiseurs Adam (implémenté à la main), SPSA (à la main) et COBYLA (`scipy.optimize`, déjà présent via Qiskit), et `shots` ;
  - gradients exacts par décalage appliqué aux probabilités : ∂p/∂θ = (p(θ+π/2) − p(θ−π/2))/2, puis la règle de chaîne pour KL et MMD ;
  - TVD avec Adam lève une `ValueError` ;
  - `baselines.py` : marginales indépendantes et arbre de Chow-Liu (arbre couvrant maximal de l'information mutuelle, par Prim), probabilités exactes, métriques, nombre de paramètres.
- **API** : kind `training` (itérations de 10 à 1000) ; résultat avec l'historique, les métriques et les deux références classiques.
- **Web** : écran « Entraînement » (courbe de perte en échelle log, distribution apprise contre cible, tableau quantique contre classique, phrase, CSV, commentaires).
- **Risque** : la durée. Une itération exacte coûte 2·P simulations par lot. Je mesurerai avant de fixer les valeurs par défaut.

## Jalon 4 : bruit simulé (`feature/m10-bruit`)

- **Bibliothèque** :
  - `noise.py`, avec l'option `noise = ["qiskit-aer"]` ;
  - profils faible, moyen et fort, ou personnalisé ;
  - `noisy_probabilities` (transpilation comme dans `hardware_cost`, simulateur Aer en matrice densité, hexagone lourd refusé) ;
  - `noisy_tvd`.
  - Les tests liés au bruit sont ignorés si Aer est absent. Pour qu'ils s'exécutent, la CI de la bibliothèque devra installer l'option.
- **API** : kind `noise` et option « évaluer sous bruit » dans `training`. Aer devient une dépendance de l'API.
- **Web** : section bruit dans l'écran Entraînement, carte « Dégradation sous bruit » dans Diagnostic.
- **Risque** : la matrice densité sur la topologie transpilée. Pour ligne, anneau et complète, le circuit garde n qubits (8 au plus, soit une matrice 256×256), ce qui reste abordable.

## Jalon 5 : base de résultats (`feature/m11-base-resultats`)

- **API** :
  - table `results` (migration), alimentée dans `RunManager._finish` pour les runs réussis de type diagnostic, training et noise ;
  - empreinte de l'ansatz = sha256 de la spec ou du QASM normalisé (pour le catalogue : nom, n et couches) ;
  - champ `share_results` sur `Project` (faux par défaut, modifiable par le propriétaire) ;
  - aucune probabilité brute du client dans `results`.
- **`scripts/build_results.py`** : grille de référence, reprise après interruption, `--limit`, `--measure` ; mesure sur 10 configurations, puis **règle des 2 heures**.
  - Taille estimée : 7 ansatz × 6 familles × qubits 2 à 6 × couches 1 à 4 × 4 évaluations, en tenant compte de Bars-and-Stripes (n = 4 et 6 seulement, et 6 dépasse la plage) : environ 7 × (5 familles × 5 n + 1) × 4 = 728 entraînements, suivis de leurs évaluations sous bruit.
  - Si l'estimation dépasse 2 heures, je m'arrête et je demande.
- **Export** CSV, et Parquet si `pyarrow` est disponible (option).

## Jalon 6 : IA de prédiction (`feature/m12-prediction`)

- **Code** : `api/stochastiq_api/ml/`, avec scikit-learn et joblib en dépendances de l'API seulement.
- **Cibles** : TVD finale exacte, et dégradation sous bruit.
- **Références à battre** : la moyenne par ansatz, et la fidélité estimée par comptage des portes.
- **Modèle** : `HistGradientBoostingRegressor`, plus deux modèles quantiles (10 % et 90 %).
- **Validations** : un ansatz laissé de côté, une famille laissée de côté, puis entraînement sur 2 à 5 qubits et test sur 6.
- **Critère** : MAE inférieure d'au moins 20 % à la référence, et couverture de l'intervalle entre 70 et 90 %. Le verdict sera rapporté tel quel ; si le critère n'est pas atteint, la référence sert de prédiction.
- **`scripts/train_predictor.py`** enregistre dans `MODELS_DIR` ; **`docs/PREDICTION.md`** donne les résultats réels.
- **Route** : `POST /projects/{id}/predict` (409 sans modèle).
- **Risque** : avec quelques centaines de lignes, le critère peut ne pas être atteint. Le verdict sera alors rapporté sans maquillage.

## Jalon 7 : recommandation et rapport (`feature/m13-recommandation`)

- **API** : kind `recommendation`, avec les règles de décision testées une par une (recouvrement des intervalles, quantique justifié ou non, indéterminé). Un entraînement réel déjà présent dans le projet prime sur la prédiction.
- **Web** : écran « Recommandation » et page « Rapport » imprimable (`@media print`), exportable en CSV et en JSON.
- **Playwright** : nouveau parcours (problème, ansatz personnalisé, entraînement, recommandation, rapport, vérification à 390 px), relancé avec l'ancien parcours.

## Jalon 8 : intégration et release (`feature/m14-release`)

- Script de démo enrichi.
- Documentation : README, API, ROLES, METRIQUES, ARCHITECTURE, CHANGELOG 0.3.0 (avec la dérogation sur le dashboard et celle sur le critère de l'IA, validée par l'auteur au jalon 6 : critère séparé entre valeur centrale et intervalle, calibrage conforme des quantiles ; voir docs/PREDICTION.md) et les deux rapports à jour.
- Versions.
- `docker compose up --build` vérifié pour de vrai, modèle présent dans le volume.
- Fusion, puis tag local `v0.3.0`.

## Jalon 9 : collecte IBM

Facultatif : **je ne le commence pas sans accord explicite de l'auteur**.

## Risques transverses

- **Durée des calculs** : le jalon 5 et la validation du jalon 6. La règle des 2 heures s'applique.
- **Durée de la suite** : la suite de la bibliothèque dure déjà environ 2 minutes. Les nouveaux tests utiliseront de petites tailles.
- **Contexte** : la mission est très longue. La conversation pourra être résumée automatiquement ; ce plan et les rapports servent de point d'ancrage.
