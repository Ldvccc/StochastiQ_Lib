import numpy as np
import pytest

from stochastiq import fit_decay, gradient_scaling, pareto_front

COLUMNS = [
    "n_qubits",
    "layers",
    "n_parameters",
    "mean_variance",
    "active_mean_variance",
    "inactive_fraction",
]


def test_pareto_un_point_domine():
    # (expressibilité, variance) : le 3e point est battu par le 1er sur les deux critères.
    points = [(0.1, 0.5), (0.05, 0.2), (0.2, 0.4)]
    assert pareto_front(points) == [True, True, False]


def test_pareto_deux_non_domines():
    assert pareto_front([(0.1, 0.1), (0.2, 0.3)]) == [True, True]


def test_pareto_egalites():
    # Points identiques : aucun ne domine l'autre.
    assert pareto_front([(0.1, 0.3), (0.1, 0.3)]) == [True, True]
    # Égal sur x, pire sur y : dominé.
    assert pareto_front([(0.1, 0.3), (0.1, 0.2)]) == [True, False]


def test_pareto_sens_des_criteres():
    points = [(1.0, 1.0), (2.0, 2.0)]
    assert pareto_front(points, minimize_x=True, maximize_y=False) == [True, False]
    assert pareto_front(points, minimize_x=False, maximize_y=True) == [False, True]


def test_fit_decay_exponentielle():
    n = np.arange(2, 9)
    fit = fit_decay(n, 0.5**n)
    assert fit["factor_per_qubit"] == pytest.approx(0.5)
    assert fit["r2"] == pytest.approx(1)
    assert fit["n_points"] == 7


def test_fit_decay_ignore_les_valeurs_nulles():
    fit = fit_decay([2, 3, 4, 5], [0.25, 0.0, 0.0625, -1.0])
    assert fit == {"factor_per_qubit": None, "r2": None, "n_points": 2}


def test_fit_decay_moins_de_3_points():
    assert fit_decay([2, 3], [0.1, 0.05])["factor_per_qubit"] is None


@pytest.mark.parametrize("mode, layers", [("fixed", [2, 2]), ("linear", [2, 3])])
def test_gradient_scaling(mode, layers):
    calls = []
    df = gradient_scaling(
        "hardware_efficient",
        range(2, 4),
        layers=2,
        layers_mode=mode,
        n_samples=20,
        seed=0,
        callback=lambda done, total: calls.append((done, total)),
    )
    assert list(df.columns) == COLUMNS
    assert len(df) == 2
    assert df["n_qubits"].tolist() == [2, 3]
    assert df["layers"].tolist() == layers
    # hardware_efficient : 2 rotations par qubit et par couche.
    assert df["n_parameters"].tolist() == [2 * n * l for n, l in zip([2, 3], layers)]
    assert (df["mean_variance"] > 0).all()
    assert (df["active_mean_variance"] >= df["mean_variance"]).all()
    assert calls == [(1, 2), (2, 2)]


def test_gradient_scaling_reproductible():
    a = gradient_scaling("brick_wall", range(2, 4), n_samples=20, seed=3)
    b = gradient_scaling("brick_wall", range(2, 4), n_samples=20, seed=3)
    assert a.equals(b)


def test_gradient_scaling_erreurs():
    with pytest.raises(ValueError, match="Mode de couches"):
        gradient_scaling("hardware_efficient", range(2, 4), layers_mode="inconnu")
    with pytest.raises(ValueError, match="vide"):
        gradient_scaling("hardware_efficient", range(2, 2))
