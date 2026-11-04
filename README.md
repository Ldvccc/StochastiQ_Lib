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

Ansatz prédéfinis (placeholders, voir `list_ansatz()`) :

```python
from stochastiq import build_ansatz, list_ansatz

print(list_ansatz())
qc = build_ansatz("ry_linear", n_qubits=4, layers=3)
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

Variance du gradient du premier paramètre (détection de plateaux stériles, coût ⟨Z₀⟩) :

```python
from stochastiq import gradient_variance

print(gradient_variance(qc, n_samples=200, seed=0))
```
