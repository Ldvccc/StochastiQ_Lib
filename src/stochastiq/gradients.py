import re

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector


def gradient_variance(
    ansatz: QuantumCircuit,
    n_samples: int = 200,
    observable: str = "Z0",
    seed: int | None = None,
) -> float:
    """Calcule la variance du gradient du premier paramètre d'un ansatz.

    Sert à détecter les plateaux stériles : une variance qui s'effondre quand
    le nombre de qubits augmente signale un paysage de coût plat. La fonction
    de coût est la valeur moyenne d'un observable local Z sur un qubit
    (``"Z0"`` : Z sur le qubit 0). Le gradient est obtenu par la règle du
    décalage de paramètre : (f(θ + π/2) - f(θ - π/2)) / 2.

    Limite : cette règle n'est exacte que si le premier paramètre est un
    angle de rotation simple (RX, RY ou RZ), utilisé une seule fois et sans
    coefficient multiplicatif. Dans les autres cas, le résultat est faux.

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit paramétré à évaluer.
    n_samples : int
        Nombre de points tirés uniformément dans [0, 2π].
    observable : str
        Observable de coût, de la forme ``"Z<k>"`` (Z sur le qubit k).
    seed : int ou None
        Graine du générateur aléatoire, pour la reproductibilité.

    Retourne
    --------
    float
        Variance empirique du gradient du premier paramètre.

    Lève
    ----
    ValueError
        Si le circuit n'a aucun paramètre libre, ou si l'observable n'est pas
        de la forme ``"Z<k>"``.
    """
    n_params = ansatz.num_parameters
    if n_params == 0:
        raise ValueError("Le circuit n'a aucun paramètre libre.")
    match = re.fullmatch(r"Z(\d+)", observable)
    if match is None:
        raise ValueError(f"Observable non supporté : {observable!r} (attendu : 'Z<k>').")
    op = SparsePauliOp.from_sparse_list([("Z", [int(match[1])], 1)], ansatz.num_qubits)

    def cost(theta: np.ndarray) -> float:
        state = Statevector(ansatz.assign_parameters(theta))
        return float(np.real(state.expectation_value(op)))

    rng = np.random.default_rng(seed)
    shift = np.zeros(n_params)
    shift[0] = np.pi / 2
    gradients = np.empty(n_samples)
    for i in range(n_samples):
        theta = rng.uniform(0, 2 * np.pi, n_params)
        gradients[i] = (cost(theta + shift) - cost(theta - shift)) / 2
    return float(np.var(gradients))
