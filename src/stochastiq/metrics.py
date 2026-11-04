import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


def expressibility(
    ansatz: QuantumCircuit,
    n_samples: int = 2000,
    n_bins: int = 75,
    seed: int | None = None,
) -> float:
    """Calcule l'expressibilité d'un ansatz paramétré.

    Implémente la mesure de Sim et al. (2019), arXiv:1905.10876 : on tire
    ``n_samples`` paires de paramètres uniformes dans [0, 2π], on calcule la
    fidélité |<ψ1|ψ2>|² entre les deux états produits, puis on compare
    l'histogramme de ces fidélités à la distribution de Haar
    P(F) = (d-1)(1-F)^(d-2), avec d = 2^n_qubits, via la divergence KL.

    Paramètres
    ----------
    ansatz : QuantumCircuit
        Circuit paramétré à évaluer.
    n_samples : int
        Nombre de paires de paramètres tirées.
    n_bins : int
        Nombre de classes de l'histogramme sur [0, 1].
    seed : int ou None
        Graine du générateur aléatoire, pour la reproductibilité.

    Retourne
    --------
    float
        Divergence KL entre la distribution des fidélités et celle de Haar.
        Plus la valeur est basse, plus l'ansatz est expressif.

    Lève
    ----
    ValueError
        Si le circuit n'a aucun paramètre libre.
    """
    n_params = ansatz.num_parameters
    if n_params == 0:
        raise ValueError("Le circuit n'a aucun paramètre libre.")

    rng = np.random.default_rng(seed)
    d = 2**ansatz.num_qubits

    fidelities = np.empty(n_samples)
    for i in range(n_samples):
        theta1 = rng.uniform(0, 2 * np.pi, n_params)
        theta2 = rng.uniform(0, 2 * np.pi, n_params)
        psi1 = Statevector(ansatz.assign_parameters(theta1))
        psi2 = Statevector(ansatz.assign_parameters(theta2))
        fidelities[i] = np.abs(np.vdot(psi1.data, psi2.data)) ** 2

    edges = np.linspace(0, 1, n_bins + 1)
    counts, _ = np.histogram(fidelities, bins=edges)
    p_ansatz = counts / n_samples

    # Probabilités de Haar par classe, via la CDF 1 - (1 - F)^(d-1).
    cdf = 1 - (1 - edges) ** (d - 1)
    p_haar = np.diff(cdf)

    eps = 1e-12
    return float(np.sum(p_ansatz * np.log((p_ansatz + eps) / (p_haar + eps))))
