"""Catalogue des ansatz et des topologies, tel que présenté par l'API."""

from stochastiq import list_ansatz, list_topologies

# nom technique -> (nom d'affichage, description, formule du nombre de paramètres)
ANSATZ_INFO: dict[str, tuple[str, str, str]] = {
    "basic_entangler": (
        "BasicEntangler",
        "RX sur chaque qubit, puis un anneau de CNOT (un seul CNOT pour 2 qubits).",
        "L·n",
    ),
    "strongly_entangling": (
        "StronglyEntangling",
        "RZ, RY, RZ sur chaque qubit, puis CNOT(i, i+r) avec une portée r qui varie selon la couche.",
        "3·L·n",
    ),
    "hardware_efficient": (
        "HardwareEfficient",
        "RY puis RZ sur chaque qubit, puis une chaîne de CNOT entre voisins.",
        "2·L·n",
    ),
    "rotation_only": ("RotationOnly", "RY sur chaque qubit, sans aucune intrication.", "L·n"),
    "all_to_all": (
        "AllToAll",
        "RX, RY, RZ sur chaque qubit, puis un CNOT pour chaque paire de qubits.",
        "3·L·n",
    ),
    "brick_wall": (
        "BrickWall",
        "RY puis RZ sur chaque qubit, puis des CNOT entre paires paires et impaires en alternance.",
        "2·L·n",
    ),
    "data_reuploading": (
        "DataReuploading",
        "RZ, RY, RZ sur chaque qubit, puis un anneau de CNOT.",
        "3·L·n",
    ),
}

TOPOLOGY_LABELS = {
    "line": "Ligne",
    "ring": "Anneau",
    "full": "Complète",
    "heavy_hex": "Hexagone lourd (19 qubits)",
}

ANSATZ_NAMES: tuple[str, ...] = tuple(list_ansatz())
TOPOLOGY_NAMES: tuple[str, ...] = tuple(list_topologies())


def ansatz_catalog() -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "label": ANSATZ_INFO[name][0],
            "description": ANSATZ_INFO[name][1],
            "parameters": ANSATZ_INFO[name][2],
        }
        for name in ANSATZ_NAMES
    ]


def topology_catalog() -> list[dict[str, str]]:
    return [{"name": name, "label": TOPOLOGY_LABELS[name]} for name in TOPOLOGY_NAMES]
