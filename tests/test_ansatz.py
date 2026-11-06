import pytest

from stochastiq import build_ansatz, list_ansatz


@pytest.mark.parametrize("name", list_ansatz())
def test_nombre_de_parametres(name):
    qc = build_ansatz(name, 4, 3)
    per_qubit = 1 if name.startswith("ry_") else 2
    assert qc.num_parameters == 3 * 4 * per_qubit


def test_nom_inconnu():
    with pytest.raises(ValueError, match="ry_linear"):
        build_ansatz("inconnu", 4, 3)


def test_list_ansatz():
    assert len(list_ansatz()) == 7
