# IA de prédiction

StochastiQ prédit, pour un ansatz, un problème et un profil de bruit :

- la **TVD finale** après un entraînement exact (KL, Adam) ;
- la **dégradation sous bruit** : la TVD sous bruit moins la TVD exacte, avec les mêmes paramètres appris.

Ce document donne les résultats réels de la validation, obtenus sur la grille de référence du 8 novembre 2026. Aucun chiffre n'est arrondi à l'avantage du modèle.

## Données

- Base de résultats (`results`), lignes éligibles : la grille de référence (`scripts/build_results.py`), plus les projets qui ont activé « Partager les résultats ». Au moment de la mesure, seule la grille était présente.
- Grille : 7 ansatz × 6 distributions de référence (Bars-and-Stripes à 4 et 6 qubits seulement) × 2 à 6 qubits × 1 à 4 couches, soit 756 configurations.
- Chaque configuration donne un entraînement exact (KL, Adam, 200 itérations, pas 0,1, graine 0), puis une évaluation des paramètres appris sous les profils faible, moyen et fort (topologie en ligne).
- Lignes par cible : 756 pour la TVD finale, 2268 pour la dégradation.
- Le calcul a pris 0,1 h avec 8 processus. La mesure préalable sur 10 configurations donnait 0,7 s en moyenne.
- Export : `data/results_grid.csv`.

Entrées du modèle :

- caractéristiques du circuit : couches, qubits, paramètres, profondeur, portes à 1 et 2 qubits, et portes du circuit transpilé sur une ligne ;
- caractéristiques du problème : entropie normalisée, fraction du support, probabilité maximale, information mutuelle moyenne ;
- pour la dégradation, les taux du profil de bruit et les portes du circuit transpilé sur la topologie du bruit.

Le modèle ne reçoit jamais l'identifiant du projet, ni le nom de l'ansatz, ni le vecteur de probabilités du client.

## Références à battre

- **Moyenne par ansatz** : moyenne de la cible pour cet ansatz (empreinte) dans le jeu d'entraînement ; moyenne globale pour un ansatz inconnu.
- **Fidélité par comptage des portes** (dégradation seulement) : F = (1 − p1)^N1 · (1 − p2)^N2 · (1 − p_lecture)^n. N1 compte les portes sx et x du circuit transpilé, N2 les cx. La dégradation est estimée par a · (1 − F), le coefficient a étant ajusté par moindres carrés sur le jeu d'entraînement.

Pour chaque validation, la référence comparée au modèle est la meilleure des deux.

## Modèle et validations

- Valeur centrale : `HistGradientBoostingRegressor` (`random_state = 0`).
- Intervalle 10-90 % : deux modèles quantiles (10 % et 90 %), même classe.

Les quatre validations regroupent les prédictions de tous leurs plis :

| Validation | Plis | Ce qu'elle simule |
|---|---|---|
| Ansatz laissé de côté | 7 | un ansatz du client jamais vu |
| Famille laissée de côté | 6 | une famille de distributions jamais vue |
| Entraînement sur 2 à 5 qubits, test sur 6 | 1 | un nombre de qubits hors de la plage apprise |
| Découpage aléatoire | 5 | un cas proche des données d'entraînement |

## Version 1 : critère initial

Critère initial : sur chacune des trois validations, un MAE au moins 20 % sous la meilleure référence et une couverture 10-90 % entre 70 et 90 %. Les modèles quantiles sont entraînés sur tout le jeu d'entraînement.

| Cible | Validation | MAE modèle | MAE référence | Gain | Couverture 10-90 % |
|---|---|---|---|---|---|
| TVD finale | Ansatz laissé de côté | 0,0736 | 0,1583 (moyenne par ansatz) | 53,5 % | 63,0 % |
| TVD finale | Famille laissée de côté | 0,1019 | 0,1418 (moyenne par ansatz) | 28,1 % | 44,2 % |
| TVD finale | 2 à 5 qubits, test sur 6 | 0,1300 | 0,1737 (moyenne par ansatz) | 25,2 % | 38,7 % |
| Dégradation | Ansatz laissé de côté | 0,0164 | 0,0365 (fidélité) | 55,0 % | 61,3 % |
| Dégradation | Famille laissée de côté | 0,0206 | 0,0391 (fidélité) | 47,4 % | 54,9 % |
| Dégradation | 2 à 5 qubits, test sur 6 | 0,0265 | 0,0538 (fidélité) | 50,8 % | 58,5 % |

Sur un découpage aléatoire, la couverture n'était que de 62,8 % (TVD finale) et 70,1 % (dégradation). Les intervalles des modèles quantiles sont trop étroits, même sans changement de distribution.

**Verdict : critère non atteint.** La précision dépasse partout la référence de plus de 20 %, mais la couverture est partout sous 70 %. Selon la règle initiale, la référence aurait servi de prédiction pour les deux cibles.

## Version 2 : critère séparé et calibrage conforme (en service)

### Dérogation au critère initial, validée par l'auteur

L'auteur a séparé le critère en deux, parce qu'il mélangeait précision et intervalles.

- **Valeur centrale** : le modèle est retenu pour une cible et une validation si son gain sur la meilleure référence atteint 20 %. C'est le cas partout : le modèle remplace la référence pour les deux cibles.
- **Intervalle** : calibrage conforme des quantiles (CQR, Romano, Patterson et Candès, 2019).
  - Les modèles quantiles sont entraînés sur 75 % du jeu d'entraînement de chaque découpage.
  - Les 25 % restants (tirage aléatoire, graine 0) servent au calibrage, jamais le jeu de test.
  - Scores E = max(q10 − y, y − q90) ; marge q̂ = ⌈(n + 1) · 0,8⌉-ième plus petit score ; intervalle [q10 − q̂, q90 + q̂].
  - Méthode fixée avant de mesurer, sans autre ajustement ensuite.
- **Affichage** : l'intervalle n'apparaît que si sa couverture mesurée sur la validation qui correspond au cas est entre 70 et 90 %. Sinon, l'écran affiche « Intervalle non fiable pour ce cas : couverture mesurée X %. »

### Résultats

Le modèle central est inchangé ; les MAE et les gains sont ceux de la version 1. La couverture « avant CQR » est celle des modèles quantiles entraînés sur 75 % du jeu, avant l'ajout de la marge.

| Cible | Validation | Gain | Couverture avant CQR | Couverture après CQR | Largeur moyenne après CQR | Intervalle affiché |
|---|---|---|---|---|---|---|
| TVD finale | Ansatz laissé de côté | 53,5 % | 61,0 % | **74,6 %** | 0,180 | oui |
| TVD finale | Famille laissée de côté | 28,1 % | 42,7 % | **52,4 %** | 0,180 | non |
| TVD finale | 2 à 5 qubits, test sur 6 | 25,2 % | 34,5 % | **39,9 %** | 0,167 | non |
| TVD finale | Découpage aléatoire | 59,4 % | 63,4 % | **79,0 %** | 0,180 | oui |
| Dégradation | Ansatz laissé de côté | 55,0 % | 58,2 % | **69,9 %** | 0,045 | non (juste sous 70 %) |
| Dégradation | Famille laissée de côté | 47,4 % | 58,3 % | **66,8 %** | 0,045 | non |
| Dégradation | 2 à 5 qubits, test sur 6 | 50,8 % | 60,7 % | **64,3 %** | 0,067 | non |
| Dégradation | Découpage aléatoire | 67,2 % | 68,8 % | **79,5 %** | 0,046 | oui |

Sur le découpage aléatoire, le MAE de la TVD finale est de 0,0541 contre 0,1332 pour la moyenne par ansatz. Celui de la dégradation est de 0,0119 contre 0,0363 pour la fidélité par comptage des portes.

Les marges CQR sont petites (de 0,0008 à 0,0046 pour la TVD finale, de 0,0004 à 0,0006 pour la dégradation), mais elles font beaucoup monter la couverture. Beaucoup de valeurs cibles sont au bord des intervalles bruts : des TVD nulles sur les distributions qu'un ansatz reproduit exactement, des dégradations nulles sur la distribution uniforme.

### Validation qui correspond au cas

Pour une prédiction, l'API détermine la situation du cas par rapport aux données d'entraînement :

- l'ansatz est inconnu (empreinte jamais vue) ;
- la famille du problème est inconnue (un problème importé en CSV est de famille « csv ») ;
- le nombre de qubits sort de la plage apprise (2 à 6).

Le cas relève des validations qui correspondent à ses situations. S'il en a plusieurs, la plus défavorable compte : la couverture la plus éloignée de 80 %, puis le gain le plus bas. S'il n'en a aucune, le découpage aléatoire compte. Cette validation décide de la source de la valeur centrale (modèle ou référence) et de l'affichage de l'intervalle.

Conséquences, avec le modèle actuel :

| Cas | TVD finale | Dégradation |
|---|---|---|
| Ansatz du catalogue, distribution de référence, 2 à 6 qubits | intervalle affiché (79,0 %) | intervalle affiché (79,5 %) |
| Ansatz personnalisé, distribution de référence, 2 à 6 qubits | intervalle affiché (74,6 %) | non fiable (69,9 %) |
| Problème importé en CSV, ou 7 à 8 qubits | non fiable (52,4 % ou 39,9 %) | non fiable (66,8 % ou 64,3 %) |

La TVD sous bruit prédite est la somme de la TVD finale et de la dégradation. Son intervalle, somme des deux intervalles, n'est donné que si les deux sont fiables.

## Verdict de la recommandation : nature de la preuve

**Dérogation validée par l'auteur (jalon 8).** Un run de recommandation, relancé après l'entraînement de HardwareEfficient sur « Gaussienne 4 qubits », concluait « Le quantique se justifie » : TVD mesurée 0,0585 contre 0,0588 pour l'arbre de Chow-Liu, soit 0,5 % d'écart, avec une seule initialisation et 16 paramètres contre 7. La valeur mesurée était traitée comme un intervalle de largeur nulle. La règle dépend désormais de la nature de la preuve de l'ansatz classé premier :

| Preuve | Règle | Verdicts |
|---|---|---|
| Valeur mesurée (entraînement du projet) | « justifié » si TVD < 0,9 × meilleure TVD classique, « non justifié » si TVD > 1,1 × | « Le quantique se justifie », « ne se justifie pas », sinon « Équivalent au classique (écart inférieur à 10 %) : le quantique n'apporte rien sur ce problème », avec le nombre de paramètres des deux côtés |
| Valeur prédite avec intervalle fiable | « justifié » si la borne haute est sous la meilleure TVD classique, « non justifié » si la borne basse est au-dessus | « se justifie », « ne se justifie pas », sinon « Indéterminé » |
| Valeur prédite sans intervalle fiable | marge m = 2 × l'erreur absolue moyenne de validation du cas comparable ; « justifié » si valeur + m < TVD classique, « non justifié » si valeur − m > TVD classique | « se justifie probablement », « ne se justifie probablement pas », sinon « Indéterminé » |

Pour une TVD sous bruit prédite (TVD finale plus dégradation), la marge vaut 2 × (MAE de la TVD finale + MAE de la dégradation). Une TVD mesurée combinée à une dégradation prédite garde l'incertitude de la mesure sur une seule initialisation (ajustements validés par l'auteur) :
- dégradation prédite avec intervalle fiable : l'intervalle [TVD mesurée + bas ; TVD mesurée + haut] est élargi de 0,1 × meilleure TVD classique de chaque côté, puis la règle des bornes s'applique. Exemple de test : TVD mesurée 0,0585, dégradation [0 ; 0,001], classique 0,0597 ; sans élargissement, la borne haute 0,0595 aurait donné « se justifie » ; avec, l'intervalle [0,0525 ; 0,0655] contient 0,0597 et le verdict est « Indéterminé » ;
- dégradation prédite sans intervalle : marge de 0,1 × meilleure TVD classique + 2 × MAE de la dégradation. Si la valeur centrale vient d'une référence (gain du modèle sous 20 %), c'est la MAE de cette référence qui compte. Une valeur mesurée n'a pas de « borne » et n'est jamais présentée comme telle.

La même règle des 10 % s'applique à la phrase de l'écran Entraînement : l'ansatz « fait mieux » que les références classiques seulement si sa TVD est sous 0,9 × la meilleure, et la référence « fait mieux » au-delà de 1,1 × ; sinon il lui est équivalent.

Pour un verdict « Indéterminé », les ansatz à entraîner sont choisis parmi les ansatz encore ouverts (aucun entraînement dans le projet, intervalle effectif contenant la meilleure TVD classique), dans l'ordre du classement, dans la limite du budget : budget // 200 entraînements de 200 itérations. Le rapport indique combien d'ansatz restent ouverts et lesquels ne sont pas proposés faute de budget. Un ansatz déjà entraîné n'est jamais proposé, même quand sa dégradation sous bruit est prédite.

Le diagnostic léger affiché par la recommandation (200 échantillons) n'entre pas dans la prédiction : les caractéristiques de l'IA sont exactes et déterministes (structure du circuit, problème, bruit), et la grille ne calcule aucun diagnostic.

Ce seuil de 10 % est une règle de lecture fixée par l'auteur, pas une quantité mesurée : il tient compte, grossièrement, de la variabilité d'une seule initialisation.

## Limites

- **Familles jamais vues.** C'est la limite principale. Le calibrage se fait sur une partie du jeu d'entraînement : il garantit la couverture pour des cas qui ressemblent à ces données, pas pour une famille de distributions absente. La couverture mesurée tombe à 52,4 % (TVD finale) et 66,8 % (dégradation). Un problème importé en CSV est toujours de famille inconnue tant qu'aucun projet qui partage ses résultats n'a fourni de lignes « csv ». Pour ces problèmes, la valeur centrale reste meilleure que la référence (gain de 28,1 % et 47,4 %), mais aucun intervalle n'est affiché.
- **Extrapolation en qubits.** Entraîné sur 2 à 5 qubits, le modèle sous-estime l'incertitude à 6 qubits (39,9 % après CQR pour la TVD finale). Les prédictions à 7 et 8 qubits sont hors de la plage de la grille.
- **Une seule initialisation.** La grille entraîne avec une seule graine. La TVD finale mesurée inclut la variabilité de l'optimisation, que le modèle ne peut pas séparer de l'effet de l'ansatz.
- **Bruit simplifié.** Profils faible, moyen et fort : des ordres de grandeur, pas des calibrations. Topologie en ligne, rz sans erreur.
- **Cas dégénérés connus.** La distribution uniforme n'est pas modifiée par ce bruit (dégradation nulle). Sur une distribution d'Ising sans champ, dont toutes les marginales valent 0,5, un ansatz sans intrication apprend la distribution uniforme et atteint exactement la référence « marginales indépendantes ».

## Reproduire

Depuis la racine du dépôt (PowerShell) :

```
.venv\Scripts\python scripts\build_results.py --database-url sqlite:///./data/results.db --measure
.venv\Scripts\python scripts\build_results.py --database-url sqlite:///./data/results.db --workers 8
.venv\Scripts\python scripts\train_predictor.py --database-url sqlite:///./data/results.db --models-dir api\models
```

Ou, à partir de l'export : `scripts\train_predictor.py --csv data\results_grid.csv`.

Le modèle est écrit dans `MODELS_DIR` (`/data/models` sous Docker) : `predictor.joblib`, plus `predictor_report.json`, qui contient tous les chiffres ci-dessus. Sans modèle, `POST /projects/{id}/predict` répond 409 « Aucun modèle entraîné ».
