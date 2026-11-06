# Métriques de StochastiQ

Ce document définit chaque mesure calculée par `stochastiq`, telle qu'elle est implémentée dans la version 0.1.0. Toutes les simulations sont exactes (vecteur d'état, sans bruit). Les paramètres sont tirés uniformément dans [0, 2π] avec `numpy.random.default_rng(seed)`.

## Expressibilité

Fonction : `expressibility(ansatz, n_samples=2000, n_bins=75, seed=None)`. L'histogramme sous-jacent est donné par `fidelity_histogram`.

Définition de Sim et al. (2019), arXiv:1905.10876 :

1. On tire `n_samples` paires de jeux de paramètres (θ, φ) et on calcule la fidélité F = |⟨ψ(θ)|ψ(φ)⟩|².
2. On construit l'histogramme P_circuit des fidélités sur `n_bins` classes de même largeur dans [0, 1].
3. La référence est la distribution des fidélités entre états de Haar aléatoires, P_Haar(F) = (d − 1)(1 − F)^(d − 2), avec d = 2^n. Sa probabilité par classe [a, b] se calcule avec la fonction de répartition 1 − (1 − F)^(d − 1).
4. L'expressibilité est la divergence de Kullback-Leibler D_KL(P_circuit ‖ P_Haar) = Σ p log(p / q), avec ε = 1e-12 ajouté au numérateur et au dénominateur pour éviter log(0).

Lecture : **plus la valeur est basse, plus l'ansatz est expressif**, car ses états couvrent l'espace de Hilbert de façon plus proche de l'uniforme.

Biais : avec un nombre fini d'échantillons, l'histogramme est bruité et la divergence est surestimée. Deux valeurs ne se comparent qu'à `n_samples` et `n_bins` égaux. Le dashboard affiche un avertissement en dessous de 1000 échantillons, et `compare(..., n_seeds=k)` donne un écart-type sur k graines.

## Capacité d'intrication (Meyer-Wallach)

Fonction : `entangling_capability(ansatz, n_samples=2000, seed=None)`.

Pour un état pur |ψ⟩ à n qubits, la mesure de Meyer-Wallach vaut

Q(ψ) = 2 · (1 − (1/n) Σ_k Tr(ρ_k²)),

où ρ_k est l'état réduit du qubit k. Q vaut 0 pour un état produit et 1 pour un état de Bell ou GHZ. La capacité d'intrication est la moyenne de Q sur `n_samples` jeux de paramètres aléatoires (Sim et al. 2019). Elle est comprise entre 0 et 1.

## Variance du gradient

Fonctions : `gradient_variance(ansatz, n_samples=200, observable="Z0", seed=None)` et `gradient_variance_details(...)`.

Coût : C(θ) = ⟨ψ(θ)| O |ψ(θ)⟩, avec deux observables possibles :

- `"Z0"` (défaut) : O = Z sur le qubit 0. C'est un observable **local** : seuls les paramètres dans le cône causal du qubit 0 influencent le coût.
- `"Zmean"` : O = (1/n) Σ_k Z_k, moyenne des Z sur tous les qubits.

Gradient : il est calculé par la **règle du décalage de paramètre**, ∂C/∂θ_p = [C(θ + (π/2) e_p) − C(θ − (π/2) e_p)] / 2. Elle est exacte pour des rotations RX, RY ou RZ dont l'angle est un paramètre seul, utilisé une seule fois. Les autres portes paramétrées lèvent une `ValueError`.

Variance : pour chaque paramètre p, on calcule la variance empirique de ∂C/∂θ_p sur `n_samples` points aléatoires (`numpy.var`, ddof = 0). On en tire :

| Clé | Définition |
|---|---|
| `variance_per_parameter` | variance de chaque paramètre, dans l'ordre de `ansatz.parameters` |
| `mean_variance` | moyenne sur **tous** les paramètres (valeur de `gradient_variance`) |
| `active_mean_variance` | moyenne sur les seuls paramètres **actifs** ; `nan` s'il n'y en a aucun |
| `n_inactive_parameters`, `inactive_fraction` | nombre et part des paramètres inactifs |

### Paramètres inactifs

Un paramètre est inactif si la variance de son gradient est inférieure à 1e-12. C'est le cas d'un RZ appliqué à |0⟩ (simple phase), ou d'un paramètre hors du cône causal de l'observable.

Avec un observable local et une profondeur fixe, la part de paramètres inactifs augmente avec le nombre de qubits. `mean_variance` baisse alors par simple **dilution**, sans perte de signal. `active_mean_variance` isole le signal lié au plateau stérile. C'est la série principale du dashboard, et elle est utilisée en ordonnée du nuage de points expressibilité / variance.

### Plateau stérile et ajustement exponentiel

`gradient_scaling(name, qubit_range, layers, layers_mode, ...)` calcule ces grandeurs pour chaque nombre de qubits n, à nombre de couches fixe (`"fixed"`) ou égal à n (`"linear"`).

`fit_decay(n_qubits, variances)` effectue une régression linéaire de log(variance) sur n, en ignorant les valeurs ≤ 0. Il retourne :

- le facteur par qubit ajouté, exp(pente) ;
- le coefficient de détermination R² ;
- le nombre de points valides. Avec moins de 3 points valides, le facteur vaut `None`.

Le dashboard ne conclut à une décroissance exponentielle nette, et n'emploie le terme « plateau stérile », que si le facteur des **paramètres actifs** est inférieur à 0,8 avec R² > 0,9. Cette conclusion vaut pour la plage de qubits étudiée et l'observable utilisée.

Références : McClean et al., « Barren plateaus in quantum neural network training landscapes », Nature Communications 9, 4812 (2018), arXiv:1803.11173. Cerezo et al., « Cost function dependent barren plateaus in shallow parametrized quantum circuits », Nature Communications 12, 1791 (2021), arXiv:2001.00550 : rôle des observables locales et globales.

## Front de Pareto

`pareto_front(points, minimize_x=True, maximize_y=True)` indique, pour chaque point (x, y), s'il est non dominé. Un point est dominé si un autre point est meilleur ou égal sur x et sur y, et strictement meilleur sur au moins l'un des deux. Deux points identiques ne se dominent pas.

Dans le Comparateur, x est l'expressibilité (à minimiser) et y la variance du gradient sur les paramètres actifs (à maximiser).

## Statistiques de circuit

`circuit_stats(ansatz)` transpile le circuit vers `["ry", "rz", "rx", "cx", "h"]`, au niveau d'optimisation 0, puis compte :

- les qubits et les paramètres ;
- la profondeur ;
- les portes à 2 qubits ;
- les portes par type.

## Coût matériel

Fonction : `hardware_cost(ansatz, topology="line", seed=None)`. La transpilation se fait hors ligne avec `qiskit.transpile`, vers les portes `["cx", "rz", "sx", "x"]`, au niveau d'optimisation 1, avec `seed_transpiler=seed`.

Trois niveaux de mesure (portes à 2 qubits et profondeur) :

| Niveau | Circuit |
|---|---|
| `before` | circuit d'origine (mêmes valeurs que `circuit_stats`) |
| `basis_only` | traduit vers les portes de base, sur un graphe de couplage complet (aucun routage) |
| `after` | transpilé sur la topologie demandée |

Surcoûts :

- `overhead_two_qubit` = portes à 2 qubits `after` / `before` ;
- `routing_overhead_two_qubit` = `after` / `basis_only`, qui isole le seul coût du routage.

Topologies (`list_topologies()`) :

- `line`, `ring` et `full` : autant de qubits que l'ansatz ;
- `heavy_hex` : réseau heavy-hex de distance 3, soit 19 qubits.

Le placement et le routage de Qiskit sont heuristiques : les résultats dépendent de la graine du transpileur. Aucune machine réelle n'est contactée.

## Conventions des ansatz

Les 7 ansatz (`list_ansatz()`) sont définis d'après le rapport QCBM Lab, section 2.4. Leur définition complète figure dans la docstring de [`src/stochastiq/ansatz.py`](../src/stochastiq/ansatz.py) : rotations par couche, entangleurs, cas n = 1 et n = 2.

Chaque couche l = 0..L−1 applique les k rotations de l'ansatz sur chaque qubit j, puis ses CNOT. Le paramètre de la rotation r du qubit j dans la couche l a l'indice ((l · n) + j) · k + r : c'est un tableau de forme (L, n, k) aplati.

`basic_entangler` et `strongly_entangling` sont vérifiés contre les gabarits PennyLane `BasicEntanglerLayers` (rotation RX) et `StronglyEntanglingLayers`. Les cinq autres sont vérifiés contre des circuits écrits avec des portes PennyLane (`tests/test_ansatz_pennylane.py`, ignoré si PennyLane n'est pas installé). Qiskit est little-endian : l'ordre des qubits est inversé avant la comparaison.
