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
