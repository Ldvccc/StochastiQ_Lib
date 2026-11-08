"""Références classiques simples, à comparer à une QCBM sur la même cible.

Les deux modèles sont ajustés exactement (maximum de vraisemblance) sur le
vecteur cible lui-même, et non sur des échantillons :

- ``independent_baseline`` : produit des marginales de chaque bit
  (n paramètres) ;
- ``chow_liu_baseline`` : arbre de Chow-Liu, qui capture les dépendances par
  paires (arbre couvrant de poids maximal pour l'information mutuelle entre
  bits, construit par l'algorithme de Prim depuis le qubit 0 ;
  1 + 2(n - 1) paramètres).

Les indices suivent la convention little-endian de Qiskit (``distributions``).
"""

import numpy as np

from .distributions import check_probabilities
from .training import distribution_metrics


def _bits(n_qubits: int) -> np.ndarray:
    states = np.arange(2**n_qubits)
    return (states[:, None] >> np.arange(n_qubits)) & 1  # (2^n, n) : bit q de chaque état


def _result(name: str, target: np.ndarray, probs: np.ndarray, n_parameters: int) -> dict:
    return {
        "name": name,
        "probabilities": probs.tolist(),
        "metrics": distribution_metrics(target, probs),
        "n_parameters": n_parameters,
    }


def independent_baseline(target) -> dict:
    """Modèle à marginales indépendantes : p(x) = Π_q p_q(x_q)."""
    target = check_probabilities(target)
    n_qubits = int(np.log2(target.size))
    bits = _bits(n_qubits)
    ones = target @ bits  # P(bit q = 1)
    probs = np.prod(np.where(bits == 1, ones, 1 - ones), axis=1)
    return _result("independent", target, probs, n_qubits)


def _pair_joint(target: np.ndarray, bits: np.ndarray, a: int, b: int) -> np.ndarray:
    """Loi jointe (2, 2) des bits a et b : joint[x_a, x_b]."""
    joint = np.zeros((2, 2))
    np.add.at(joint, (bits[:, a], bits[:, b]), target)
    return joint


def _mutual_information(joint: np.ndarray) -> float:
    pa, pb = joint.sum(axis=1), joint.sum(axis=0)
    outer = np.outer(pa, pb)
    mask = joint > 0
    return float((joint[mask] * np.log(joint[mask] / outer[mask])).sum())


def chow_liu_tree(target) -> list[tuple[int, int]]:
    """Arêtes (parent, enfant) de l'arbre de Chow-Liu, enraciné au qubit 0."""
    target = check_probabilities(target)
    n_qubits = int(np.log2(target.size))
    bits = _bits(n_qubits)
    weights = np.zeros((n_qubits, n_qubits))
    for a in range(n_qubits):
        for b in range(a + 1, n_qubits):
            weights[a, b] = weights[b, a] = _mutual_information(_pair_joint(target, bits, a, b))
    in_tree = {0}
    edges: list[tuple[int, int]] = []
    while len(in_tree) < n_qubits:
        # Arête de poids maximal entre l'arbre et le reste (égalités : plus petits indices).
        parent, child = max(
            ((p, c) for p in sorted(in_tree) for c in range(n_qubits) if c not in in_tree),
            key=lambda e: (weights[e[0], e[1]], -e[0], -e[1]),
        )
        edges.append((parent, child))
        in_tree.add(child)
    return edges


def chow_liu_baseline(target) -> dict:
    """Arbre de Chow-Liu : p(x) = p(x_0) Π p(x_enfant | x_parent)."""
    target = check_probabilities(target)
    n_qubits = int(np.log2(target.size))
    bits = _bits(n_qubits)
    root_one = target @ bits[:, 0]
    probs = np.where(bits[:, 0] == 1, root_one, 1 - root_one)
    for parent, child in chow_liu_tree(target):
        joint = _pair_joint(target, bits, parent, child)
        parent_marginal = joint.sum(axis=1)
        # p(enfant | parent) ; un parent de probabilité nulle ne contribue pas.
        conditional = np.divide(joint, parent_marginal[:, None], out=np.full((2, 2), 0.5), where=parent_marginal[:, None] > 0)
        probs = probs * conditional[bits[:, parent], bits[:, child]]
    return _result("chow_liu", target, probs, 1 + 2 * (n_qubits - 1))


def classical_baselines(target) -> dict:
    """Les deux références classiques : ``{"independent": ..., "chow_liu": ...}``."""
    return {"independent": independent_baseline(target), "chow_liu": chow_liu_baseline(target)}
