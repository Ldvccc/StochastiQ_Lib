# StochastiQ

`stochastiq` mesure l'expressibilité d'un ansatz Qiskit, selon la définition de Sim et al. (2019).

## Installation

Depuis GitHub :

```bash
pip install "git+https://github.com/Ldvccc/StochastiQ_Lib.git"
```

En local (développement) :

```bash
pip install -e ".[dev]"
pytest
```

## Exemple

```python
from qiskit.circuit.library import real_amplitudes
from stochastiq import expressibility

ansatz = real_amplitudes(4, reps=3)
print(expressibility(ansatz, seed=0))  # plus bas = plus expressif
```

## Autres fonctionnalités

Les 7 ansatz de QCBM Lab (`basic_entangler`, `strongly_entangling`, `hardware_efficient`, `rotation_only`, `all_to_all`, `brick_wall`, `data_reuploading`), définis d'après le rapport QCBM Lab, section 2.4 (voir la docstring de `stochastiq.ansatz`) :

```python
from stochastiq import build_ansatz, list_ansatz

print(list_ansatz())
qc = build_ansatz("hardware_efficient", n_qubits=4, layers=3)
```

Leur vérification contre PennyLane (`BasicEntanglerLayers`, `StronglyEntanglingLayers` et des circuits de référence écrits avec des portes PennyLane) demande l'option `verify` :

```bash
pip install -e ".[dev,verify]"
pytest tests/test_ansatz_pennylane.py
```

Capacité d'intrication (Meyer-Wallach moyenne, entre 0 et 1) :

```python
from stochastiq import entangling_capability

print(entangling_capability(qc, seed=0))
```

Statistiques du circuit (après transpilation vers `ry, rz, rx, cx, h`) :

```python
from stochastiq import circuit_stats

print(circuit_stats(qc))  # n_qubits, n_parameters, depth, n_two_qubit_gates, gate_counts
```

Variance du gradient (détection de plateaux stériles), calculée pour chaque paramètre par la règle du décalage de paramètre puis moyennée sur tous les paramètres. Coût `"Z0"` (⟨Z⟩ sur le qubit 0, local, par défaut) ou `"Zmean"` (moyenne des ⟨Z⟩ sur tous les qubits) :

```python
from stochastiq import gradient_variance, gradient_variance_details

print(gradient_variance(qc, n_samples=200, seed=0))
details = gradient_variance_details(qc, observable="Zmean", seed=0)
# mean_variance, variance_per_parameter, n_inactive_parameters, inactive_fraction
```

Un paramètre est inactif si la variance de son gradient est inférieure à 1e-12 (RZ appliqué à |0⟩, paramètre hors du cône causal de l'observable).

Comparaison de plusieurs ansatz (DataFrame trié par expressibilité croissante) :

```python
from stochastiq import compare

circuits = {name: build_ansatz(name, 4, 3) for name in list_ansatz()}
print(compare(circuits, n_samples=500, seed=0))
```

Histogramme des fidélités et référence de Haar (probabilités par classe) :

```python
from stochastiq import fidelity_histogram

hist = fidelity_histogram(qc, seed=0)  # {"edges", "circuit", "haar"}
```

Coût de transpilation hors ligne sur une topologie (`list_topologies()`) :

```python
from stochastiq import hardware_cost

print(hardware_cost(qc, topology="heavy_hex", seed=0))
```

`compare(..., n_seeds=5)` répète chaque métrique sur 5 graines et ajoute les colonnes `<métrique>_std`. La colonne `inactive_fraction` donne la part des paramètres inactifs (coût `"Z0"`).

Variance du gradient en fonction du nombre de qubits (détection d'un plateau stérile) et ajustement exponentiel :

```python
from stochastiq import fit_decay, gradient_scaling

df = gradient_scaling("hardware_efficient", range(2, 7), layers=3, n_samples=100, seed=0)
print(fit_decay(df["n_qubits"], df["mean_variance"]))  # factor_per_qubit, r2, n_points
```

`layers_mode="linear"` utilise autant de couches que de qubits. `pareto_front(points)` indique les points (expressibilité, variance du gradient) non dominés.

## Dashboard

```bash
pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

Voir [dashboard/README.md](dashboard/README.md).
