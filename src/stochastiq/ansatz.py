"""Construction d'ansatz paramétrés.

Les 7 circuits définis ici sont des PLACEHOLDERS : ils devront être alignés
plus tard sur les vrais ansatz du projet.
"""

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector

# nom -> (rotations appliquées sur chaque qubit, connectivité des CNOT)
_ANSATZ = {
    "ry_linear": (("ry",), "linear"),
    "ry_circular": (("ry",), "circular"),
    "ry_full": (("ry",), "full"),
    "ryrz_linear": (("ry", "rz"), "linear"),
    "ryrz_circular": (("ry", "rz"), "circular"),
    "ryrz_full": (("ry", "rz"), "full"),
    # Provisoire.
    "strongly_entangling": (("ry", "rz"), "circular"),
}


def list_ansatz() -> list[str]:
    """Retourne la liste des noms d'ansatz disponibles."""
    return list(_ANSATZ)


def _cnot_pairs(entanglement: str, n_qubits: int) -> list[tuple[int, int]]:
    if entanglement == "linear" or (entanglement == "circular" and n_qubits <= 2):
        return [(i, i + 1) for i in range(n_qubits - 1)]
    if entanglement == "circular":
        return [(i, (i + 1) % n_qubits) for i in range(n_qubits)]
    return [(i, j) for i in range(n_qubits) for j in range(i + 1, n_qubits)]


def build_ansatz(name: str, n_qubits: int, layers: int) -> QuantumCircuit:
    """Construit un ansatz paramétré à partir de son nom.

    Chaque couche applique les rotations de l'ansatz (RY, ou RY puis RZ) sur
    chaque qubit, puis des CNOT selon la connectivité : linéaire (i → i+1),
    circulaire (i → (i+1) % n, un seul CNOT si n = 2) ou complète (toutes
    les paires i < j).

    Paramètres
    ----------
    name : str
        Nom de l'ansatz, parmi ``list_ansatz()``.
    n_qubits : int
        Nombre de qubits.
    layers : int
        Nombre de couches.

    Retourne
    --------
    QuantumCircuit
        Circuit à ``layers * n_qubits`` paramètres (``ry_*``) ou
        ``layers * n_qubits * 2`` (``ryrz_*`` et ``strongly_entangling``).

    Lève
    ----
    ValueError
        Si le nom est inconnu.
    """
    if name not in _ANSATZ:
        raise ValueError(
            f"Ansatz inconnu : {name!r}. Noms valides : {', '.join(list_ansatz())}."
        )

    rotations, entanglement = _ANSATZ[name]
    theta = ParameterVector("θ", layers * n_qubits * len(rotations))
    qc = QuantumCircuit(n_qubits, name=name)
    k = 0
    for _ in range(layers):
        for q in range(n_qubits):
            for rotation in rotations:
                getattr(qc, rotation)(theta[k], q)
                k += 1
        for control, target in _cnot_pairs(entanglement, n_qubits):
            qc.cx(control, target)
    return qc
