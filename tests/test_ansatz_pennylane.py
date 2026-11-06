"""Vérification des ansatz Qiskit contre des circuits PennyLane de référence.

basic_entangler et strongly_entangling sont comparés aux gabarits
PennyLane (BasicEntanglerLayers, StronglyEntanglingLayers) ; les autres
ansatz, sans gabarit, sont réécrits directement avec des portes PennyLane.
"""

import numpy as np
import pytest
from qiskit.quantum_info import Statevector

from stochastiq import build_ansatz, list_ansatz

qml = pytest.importorskip("pennylane")

# Nombre de rotations par qubit (dernier axe des poids de forme (L, n, k)).
K = {
    "basic_entangler": 1,
    "strongly_entangling": 3,
    "hardware_efficient": 2,
    "rotation_only": 1,
    "all_to_all": 3,
    "brick_wall": 2,
    "data_reuploading": 3,
}


def _reference(name: str, weights: np.ndarray) -> None:
    L, n, _ = weights.shape
    wires = list(range(n))
    if name == "basic_entangler":
        qml.BasicEntanglerLayers(weights[:, :, 0], wires=wires, rotation=qml.RX)
        return
    if name == "strongly_entangling":
        qml.StronglyEntanglingLayers(weights, wires=wires)
        return

    gates = {
        "hardware_efficient": [qml.RY, qml.RZ],
        "rotation_only": [qml.RY],
        "all_to_all": [qml.RX, qml.RY, qml.RZ],
        "brick_wall": [qml.RY, qml.RZ],
        "data_reuploading": [qml.RZ, qml.RY, qml.RZ],
    }[name]
    for l in range(L):
        for j in range(n):
            for r, gate in enumerate(gates):
                gate(weights[l, j, r], wires=j)
        if name == "hardware_efficient":
            for i in range(n - 1):
                qml.CNOT(wires=[i, i + 1])
        elif name == "all_to_all":
            for i in range(n):
                for j in range(i + 1, n):
                    qml.CNOT(wires=[i, j])
        elif name == "brick_wall":
            for i in range(l % 2, n - 1, 2):
                qml.CNOT(wires=[i, i + 1])
        elif name == "data_reuploading":
            for i in range(n):
                qml.CNOT(wires=[i, (i + 1) % n])


def _pennylane_probs(name: str, weights: np.ndarray) -> np.ndarray:
    n = weights.shape[1]
    device = qml.device("default.qubit", wires=n)

    @qml.qnode(device)
    def circuit():
        _reference(name, weights)
        return qml.probs(wires=range(n))

    return np.asarray(circuit())


def _qiskit_probs(name: str, weights: np.ndarray) -> np.ndarray:
    L, n, _ = weights.shape
    qc = build_ansatz(name, n, L)
    probs = Statevector(qc.assign_parameters(weights.ravel())).probabilities()
    # Qiskit est little-endian (qubit 0 = bit de poids faible) ; PennyLane
    # place le fil 0 en bit de poids fort : on inverse l'ordre des qubits.
    return probs.reshape([2] * n).transpose().ravel()


@pytest.mark.parametrize("name", list_ansatz())
@pytest.mark.parametrize("n_qubits", [2, 3, 4])
@pytest.mark.parametrize("layers", [1, 2, 3])
def test_memes_probabilites_que_pennylane(name, n_qubits, layers):
    rng = np.random.default_rng(1000 * n_qubits + 10 * layers + list_ansatz().index(name))
    weights = rng.uniform(0, 2 * np.pi, (layers, n_qubits, K[name]))
    np.testing.assert_allclose(
        _qiskit_probs(name, weights), _pennylane_probs(name, weights), atol=1e-10
    )
