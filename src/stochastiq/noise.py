"""Bruit simulé (option ``noise`` : qiskit-aer).

Le circuit est transpilé comme dans ``hardware_cost`` (portes cx, rz, sx et x,
niveau d'optimisation 1, ``seed_transpiler``), puis simulé en matrice densité
avec un modèle de bruit paramétrique :

- dépolarisation à 1 qubit de taux ``p1`` sur les portes sx et x (la porte rz
  est supposée virtuelle, donc sans erreur, comme sur les machines IBM) ;
- dépolarisation à 2 qubits de taux ``p2`` sur cx ;
- erreur de lecture symétrique de taux ``readout`` sur chaque qubit.

Les profils faible, moyen et fort donnent des **ordres de grandeur**, pas des
calibrations de machines réelles. Les probabilités sont remises dans l'ordre
logique des qubits (convention little-endian de Qiskit) grâce au placement
final du transpileur.

Topologies : ligne, anneau et complète (autant de qubits que l'ansatz).
L'hexagone lourd (19 qubits) est refusé : une matrice densité de 2^19 × 2^19
coefficients n'est pas simulable ici.
"""

from collections.abc import Mapping

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.transpiler import CouplingMap

from .gradients import batched_probabilities

PROFILES: dict[str, dict[str, float]] = {
    "faible": {"p1": 1e-4, "p2": 5e-4, "readout": 1e-3},
    "moyen": {"p1": 1e-3, "p2": 5e-3, "readout": 1e-2},
    "fort": {"p1": 1e-2, "p2": 2e-2, "readout": 5e-2},
}
NOISE_TOPOLOGIES = ("line", "ring", "full")
_BASIS_GATES = ["cx", "rz", "sx", "x"]
MAX_RATE = 0.5


def resolve_profile(profile: str | Mapping[str, float]) -> dict[str, float]:
    """Taux d'un profil nommé (faible, moyen, fort) ou personnalisé ``{p1, p2, readout}``."""
    if isinstance(profile, str):
        if profile not in PROFILES:
            raise ValueError(f"Profil de bruit inconnu : {profile!r}. Profils : {', '.join(PROFILES)} ou personnalisé.")
        return dict(PROFILES[profile])
    if not isinstance(profile, Mapping) or set(profile) != {"p1", "p2", "readout"}:
        raise ValueError("Un profil personnalisé doit fournir exactement p1, p2 et readout.")
    rates = {key: float(value) for key, value in profile.items()}
    for key, value in rates.items():
        if not 0 <= value <= MAX_RATE:
            raise ValueError(f"Le taux {key} doit être compris entre 0 et {MAX_RATE}.")
    return rates


def noise_model(profile: str | Mapping[str, float]):
    """Modèle de bruit Aer correspondant au profil (sans l'erreur de lecture, appliquée à part)."""
    from qiskit_aer.noise import NoiseModel, depolarizing_error

    rates = resolve_profile(profile)
    model = NoiseModel(basis_gates=_BASIS_GATES)
    if rates["p1"] > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(rates["p1"], 1), ["sx", "x"])
    if rates["p2"] > 0:
        model.add_all_qubit_quantum_error(depolarizing_error(rates["p2"], 2), ["cx"])
    return model


def _coupling_map(topology: str, n_qubits: int) -> CouplingMap:
    if topology == "heavy_hex":
        raise ValueError(
            "Le bruit n'est pas simulable sur l'hexagone lourd : 19 qubits, soit une matrice densité "
            "de 2^19 × 2^19 coefficients. Choisissez ligne, anneau ou complète."
        )
    builders = {"line": CouplingMap.from_line, "ring": CouplingMap.from_ring, "full": CouplingMap.from_full}
    if topology not in builders:
        raise ValueError(f"Topologie inconnue : {topology!r}. Topologies : {', '.join(NOISE_TOPOLOGIES)}.")
    return builders[topology](n_qubits)


def _apply_readout(probs: np.ndarray, n_qubits: int, readout: float) -> np.ndarray:
    """Erreur de lecture symétrique, qubit par qubit (axe n-1-q pour le qubit q)."""
    if readout == 0:
        return probs
    confusion = np.array([[1 - readout, readout], [readout, 1 - readout]])  # [mesuré, vrai]
    tensor = probs.reshape([2] * n_qubits)
    for axis in range(n_qubits):
        tensor = np.moveaxis(np.tensordot(confusion, tensor, axes=([1], [axis])), 0, axis)
    return tensor.reshape(-1)


def _compile(ansatz: QuantumCircuit, topology: str, seed: int | None) -> QuantumCircuit:
    """Transpilation commune au bruit et aux comptes de portes (portes cx, rz, sx et x)."""
    coupling = _coupling_map(topology, ansatz.num_qubits)
    return transpile(
        ansatz, basis_gates=_BASIS_GATES, coupling_map=coupling, optimization_level=1, seed_transpiler=seed
    )


def transpiled_gate_counts(ansatz: QuantumCircuit, topology: str = "line", seed: int | None = 0) -> dict:
    """Portes du circuit transpilé comme pour le bruit (paramètres laissés libres).

    Retourne ``n1`` (portes sx et x, les seules à porter une erreur à 1 qubit),
    ``n2`` (portes cx) et ``depth``. Ne demande pas qiskit-aer.
    """
    compiled = _compile(ansatz, topology, seed)
    ops = compiled.count_ops()
    return {"n1": int(ops.get("sx", 0) + ops.get("x", 0)), "n2": int(ops.get("cx", 0)), "depth": compiled.depth()}


def gate_count_fidelity(counts: Mapping[str, int], profile: str | Mapping[str, float], n_qubits: int) -> float:
    """Fidélité estimée par comptage des portes : (1 - p1)^n1 · (1 - p2)^n2 · (1 - lecture)^n.

    Référence grossière (erreurs indépendantes, pas d'annulation) ; ``counts``
    vient de ``transpiled_gate_counts``.
    """
    rates = resolve_profile(profile)
    return float((1 - rates["p1"]) ** counts["n1"] * (1 - rates["p2"]) ** counts["n2"] * (1 - rates["readout"]) ** n_qubits)


def noisy_probabilities(
    ansatz: QuantumCircuit,
    params,
    profile: str | Mapping[str, float],
    topology: str = "full",
    seed: int | None = None,
) -> np.ndarray:
    """Distribution de mesure bruitée de l'ansatz pour les paramètres ``params``.

    ``params`` suit l'ordre de ``ansatz.parameters``. Le résultat est un vecteur
    de 2^n probabilités, dans l'ordre logique des qubits.
    """
    from qiskit_aer import AerSimulator
    import qiskit_aer.library  # noqa: F401  (ajoute QuantumCircuit.save_probabilities)

    rates = resolve_profile(profile)
    n_qubits = ansatz.num_qubits
    compiled = _compile(ansatz.assign_parameters(np.asarray(params, dtype=float)), topology, seed)
    physical = compiled.layout.final_index_layout() if compiled.layout is not None else list(range(n_qubits))
    compiled.save_probabilities(physical)
    simulator = AerSimulator(method="density_matrix", noise_model=noise_model(rates), seed_simulator=seed)
    probs = np.asarray(simulator.run(compiled).result().data()["probabilities"], dtype=float)
    probs = _apply_readout(probs, n_qubits, rates["readout"])
    probs = np.clip(probs, 0, None)
    return probs / probs.sum()


def noisy_tvd(
    ansatz: QuantumCircuit,
    profile: str | Mapping[str, float],
    topology: str = "full",
    n_samples: int = 20,
    seed: int | None = None,
) -> dict:
    """TVD moyenne entre sortie idéale et sortie bruitée, sur des paramètres aléatoires.

    Les paramètres sont tirés uniformément dans [0, 2π] (``default_rng(seed)``).
    Retourne ``mean_tvd``, ``std_tvd``, ``tvds`` (une valeur par tirage),
    ``profile`` (taux utilisés) et ``topology``.
    """
    if n_samples < 1:
        raise ValueError("n_samples doit valoir au moins 1.")
    rates = resolve_profile(profile)
    rng = np.random.default_rng(seed)
    thetas = rng.uniform(0, 2 * np.pi, (n_samples, ansatz.num_parameters))
    ideal = batched_probabilities(ansatz, thetas)
    tvds = [
        float(0.5 * np.abs(noisy_probabilities(ansatz, theta, rates, topology, seed) - ideal[i]).sum())
        for i, theta in enumerate(thetas)
    ]
    return {
        "mean_tvd": float(np.mean(tvds)),
        "std_tvd": float(np.std(tvds, ddof=1)) if len(tvds) > 1 else 0.0,
        "tvds": tvds,
        "profile": rates,
        "topology": topology,
    }
