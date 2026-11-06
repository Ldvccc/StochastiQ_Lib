from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from stochastiq_api.db import Base, make_engine, upgrade_database
from stochastiq_api import models  # noqa: F401


def test_migrations_conformes_aux_modeles(tmp_path):
    url = f"sqlite:///{tmp_path / 'migr.db'}"
    upgrade_database(url)
    engine = make_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []
