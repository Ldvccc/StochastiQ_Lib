import math

from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap

from .stats import circuit_stats

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
    d'optimisation 1. Trois niveaux de mesure sont retournés :

    - ``before`` : le circuit d'origine (mêmes valeurs que ``circuit_stats``) ;
    - ``basis_only`` : traduction vers les portes de base sur un graphe de
      couplage complet, donc sans routage ;
    - ``after`` : transpilation sur la topologie demandée.

    Le rapport ``after`` / ``basis_only`` isole le coût du routage. Les
    topologies ``line``, ``ring`` et ``full`` ont autant de qubits que
    l'ansatz ; ``heavy_hex`` est le réseau heavy-hex de distance 3 (19 qubits).

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
        ``topology`` ; ``before``, ``basis_only`` et ``after``, chacun un dict
        ``{"n_two_qubit_gates", "depth"}`` ; les clés à plat
        ``n_two_qubit_gates_before``, ``depth_before`` (circuit d'origine),
        ``n_two_qubit_gates_after``, ``depth_after`` ; ``overhead_two_qubit``
        (portes à 2 qubits after / before, ``nan`` si le circuit d'origine
        n'en a aucune) et ``routing_overhead_two_qubit`` (after / basis_only).

    Lève
    ----
    ValueError
        Si la topologie est inconnue ou a moins de qubits que l'ansatz, ou si
        le circuit traduit n'a aucune porte à 2 qubits (surcoût du routage
        non défini).
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

    stats = circuit_stats(ansatz)
    before = {"n_two_qubit_gates": stats["n_two_qubit_gates"], "depth": stats["depth"]}

    def _transpiled(target: CouplingMap) -> dict:
        qc = transpile(
            ansatz,
            basis_gates=_BASIS_GATES,
            coupling_map=target,
            optimization_level=1,
            seed_transpiler=seed,
        )
        return {"n_two_qubit_gates": _two_qubit_gates(qc), "depth": qc.depth()}

    basis_only = _transpiled(CouplingMap.from_full(ansatz.num_qubits))
    after = _transpiled(coupling_map)
    if basis_only["n_two_qubit_gates"] == 0:
        raise ValueError(
            "Le circuit traduit n'a aucune porte à 2 qubits : surcoût du routage non défini."
        )

    n_before = before["n_two_qubit_gates"]
    return {
        "topology": topology,
        "before": before,
        "basis_only": basis_only,
        "after": after,
        "n_two_qubit_gates_before": n_before,
        "n_two_qubit_gates_after": after["n_two_qubit_gates"],
        "depth_before": before["depth"],
        "depth_after": after["depth"],
        "overhead_two_qubit": after["n_two_qubit_gates"] / n_before if n_before else math.nan,
        "routing_overhead_two_qubit": after["n_two_qubit_gates"] / basis_only["n_two_qubit_gates"],
    }
