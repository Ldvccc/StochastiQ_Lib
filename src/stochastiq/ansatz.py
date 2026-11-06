"""Construction des ansatz de QCBM Lab.

Définitions d'après le rapport QCBM Lab, section 2.4. Pour n qubits et L
couches, chaque couche l = 0..L-1 applique d'abord les k rotations de
l'ansatz sur chaque qubit j, puis ses entangleurs. Le paramètre de la
rotation r du qubit j dans la couche l a l'indice ((l * n) + j) * k + r :
c'est un tableau de forme (L, n, k) aplati.

- ``basic_entangler`` : RX ; CNOT(i, (i+1) % n) pour i = 0..n-1 si n > 2,
  un seul CNOT(0, 1) si n = 2, aucun si n = 1. Paramètres : L·n.
- ``strongly_entangling`` : RZ(φ), RY(θ), RZ(ω) ; CNOT(i, (i+r) % n) pour
  tout i, avec r = (l % (n-1)) + 1 (aucun si n = 1). Paramètres : 3·L·n.
- ``hardware_efficient`` : RY, RZ ; CNOT(i, i+1) pour i = 0..n-2.
  Paramètres : 2·L·n, CNOT : (n-1)·L.
- ``rotation_only`` : RY ; aucun CNOT. Paramètres : L·n.
- ``all_to_all`` : RX, RY, RZ ; CNOT(i, j) pour toutes les paires i < j.
  Paramètres : 3·L·n, CNOT : n(n-1)/2 · L.
- ``brick_wall`` : RY, RZ ; couche paire : CNOT(i, i+1) pour i = 0, 2, 4...,
  couche impaire : i = 1, 3, 5... (tant que i+1 < n). Paramètres : 2·L·n.
- ``data_reuploading`` : RZ, RY, RZ ; anneau CNOT(i, (i+1) % n) pour
  i = 0..n-1. Paramètres : 3·L·n, CNOT : n·L. Pour n = 2, l'anneau donne
  CNOT(0, 1) puis CNOT(1, 0) (deux CNOT de sens opposés, toujours n·L) ;
  aucun CNOT pour n = 1.
"""

from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector


def _ring(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    if n_qubits < 2:
        return []
    return [(i, (i + 1) % n_qubits) for i in range(n_qubits)]


def _basic_ring(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    if n_qubits == 2:
        return [(0, 1)]
    return _ring(n_qubits, layer)


def _strongly_ranges(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    if n_qubits < 2:
        return []
    r = (layer % (n_qubits - 1)) + 1
    return [(i, (i + r) % n_qubits) for i in range(n_qubits)]


def _linear(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    return [(i, i + 1) for i in range(n_qubits - 1)]


def _none(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    return []


def _all_pairs(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n_qubits) for j in range(i + 1, n_qubits)]


def _brick(n_qubits: int, layer: int) -> list[tuple[int, int]]:
    return [(i, i + 1) for i in range(layer % 2, n_qubits - 1, 2)]


# nom -> (rotations appliquées sur chaque qubit, CNOT de la couche l)
_ANSATZ = {
    "basic_entangler": (("rx",), _basic_ring),
    "strongly_entangling": (("rz", "ry", "rz"), _strongly_ranges),
    "hardware_efficient": (("ry", "rz"), _linear),
    "rotation_only": (("ry",), _none),
    "all_to_all": (("rx", "ry", "rz"), _all_pairs),
    "brick_wall": (("ry", "rz"), _brick),
    "data_reuploading": (("rz", "ry", "rz"), _ring),
}


def list_ansatz() -> list[str]:
    """Retourne la liste des noms d'ansatz disponibles."""
    return list(_ANSATZ)


def build_ansatz(name: str, n_qubits: int, layers: int) -> QuantumCircuit:
    """Construit un ansatz QCBM Lab à partir de son nom.

    Voir la docstring du module pour la définition de chaque ansatz et
    l'ordre des paramètres.

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
        Circuit à ``layers * n_qubits * k`` paramètres, k étant le nombre de
        rotations par qubit de l'ansatz.

    Lève
    ----
    ValueError
        Si le nom est inconnu.
    """
    if name not in _ANSATZ:
        raise ValueError(
            f"Ansatz inconnu : {name!r}. Noms valides : {', '.join(list_ansatz())}."
        )

    rotations, entanglers = _ANSATZ[name]
    k = len(rotations)
    theta = ParameterVector("θ", layers * n_qubits * k)
    qc = QuantumCircuit(n_qubits, name=name)
    for layer in range(layers):
        for j in range(n_qubits):
            for r, rotation in enumerate(rotations):
                getattr(qc, rotation)(theta[(layer * n_qubits + j) * k + r], j)
        for control, target in entanglers(n_qubits, layer):
            qc.cx(control, target)
    return qc


def ansatz_structure(name: str, n_qubits: int, layers: int) -> dict:
    """Décrit un ansatz sous forme structurée, pour le dessiner (par exemple côté web).

    Le circuit est découpé en colonnes, dans l'ordre d'exécution : pour
    chaque couche, une colonne par rotation (la r-ième rotation de tous les
    qubits), puis une colonne par CNOT. Les portes et l'ordre des paramètres
    sont ceux de ``build_ansatz``.

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
    dict
        ``{"n_qubits", "layers", "columns"}``, où ``columns`` est une liste de
        ``{"gates": [...]}`` et chaque porte vaut ``{"type": "RX" | "RY" | "RZ"
        | "CNOT", "qubits": [...], "param_index": int ou None}``. Pour un
        CNOT, ``qubits`` vaut ``[contrôle, cible]`` et ``param_index`` None.

    Lève
    ----
    ValueError
        Si le nom est inconnu.
    """
    if name not in _ANSATZ:
        raise ValueError(
            f"Ansatz inconnu : {name!r}. Noms valides : {', '.join(list_ansatz())}."
        )

    rotations, entanglers = _ANSATZ[name]
    k = len(rotations)
    columns = []
    for layer in range(layers):
        for r, rotation in enumerate(rotations):
            columns.append(
                {
                    "gates": [
                        {
                            "type": rotation.upper(),
                            "qubits": [j],
                            "param_index": (layer * n_qubits + j) * k + r,
                        }
                        for j in range(n_qubits)
                    ]
                }
            )
        for control, target in entanglers(n_qubits, layer):
            columns.append(
                {"gates": [{"type": "CNOT", "qubits": [control, target], "param_index": None}]}
            )
    return {"n_qubits": n_qubits, "layers": layers, "columns": columns}
