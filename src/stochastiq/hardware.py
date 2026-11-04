import math

from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap

_BASIS_GATES = ["cx", "rz", "sx", "x"]

_TOPOLOGIES = {
    "line": CouplingMap.from_line,
    "ring": CouplingMap.from_ring,
    "full": CouplingMap.from_full,
    "heavy_hex": lambda n_qubits: CouplingMap.from_heavy_hex(distance=3),
}


def list_topologies() -> list[str]:
    """Retourne la liste des topologies matérielles disponibles."""
    return list(_TOPOLOGIES)


def _two_qubit_gates(qc: QuantumCircuit) -> int:
    return sum(
        1
        for instruction in qc.data
        if instruction.operation.num_qubits == 2 and instruction.operation.name != "barrier"
    )


def hardware_cost(
    ansatz: QuantumCircuit,
    topology: str = "line",
    seed: int | None = None,
) -> dict:
    """Estime le surcoût de transpilation d'un ansatz sur une topologie donnée.

    Transpilation hors ligne (aucune connexion à une machine réelle) avec
    ``qiskit.transpile``, vers les portes ``["cx", "rz", "sx", "x"]``, niveau
    d'optimisation 1. La référence « avant » est le même circuit transpilé
    vers les mêmes portes, sans contrainte de connectivité : la différence
    mesure donc le seul coût du routage. Les topologies ``line``, ``ring`` et
    ``full`` ont autant de qubits que l'ansatz ; ``heavy_hex`` est le réseau
    heavy-hex de distance 3 (19 qubits).

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit à transpiler.
    topology : str
        Nom de la topologie, parmi ``list_topologies()``.
    seed : int ou None
        Graine du transpileur (``seed_transpiler``), pour la reproductibilité.

    Retourne
    --------
    dict
        ``topology``, ``n_two_qubit_gates_before``, ``n_two_qubit_gates_after``,
        ``depth_before``, ``depth_after`` et ``overhead_two_qubit``
        (after / before, ``nan`` si le circuit n'a aucune porte à 2 qubits).

    Lève
    ----
    ValueError
        Si la topologie est inconnue ou a moins de qubits que l'ansatz.
    """
    if topology not in _TOPOLOGIES:
        raise ValueError(
            f"Topologie inconnue : {topology!r}. Noms valides : {', '.join(list_topologies())}."
        )
    coupling_map = _TOPOLOGIES[topology](ansatz.num_qubits)
    if coupling_map.size() < ansatz.num_qubits:
        raise ValueError(
            f"La topologie {topology!r} a {coupling_map.size()} qubits, "
            f"l'ansatz en demande {ansatz.num_qubits}."
        )

    before = transpile(
        ansatz, basis_gates=_BASIS_GATES, optimization_level=1, seed_transpiler=seed
    )
    after = transpile(
        ansatz,
        basis_gates=_BASIS_GATES,
        coupling_map=coupling_map,
        optimization_level=1,
        seed_transpiler=seed,
    )
    n_before = _two_qubit_gates(before)
    n_after = _two_qubit_gates(after)
    return {
        "topology": topology,
        "n_two_qubit_gates_before": n_before,
        "n_two_qubit_gates_after": n_after,
        "depth_before": before.depth(),
        "depth_after": after.depth(),
        "overhead_two_qubit": n_after / n_before if n_before else math.nan,
    }
