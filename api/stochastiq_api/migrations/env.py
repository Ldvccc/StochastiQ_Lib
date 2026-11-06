from alembic import context

from stochastiq_api import models  # noqa: F401  (enregistre les tables)
from stochastiq_api.config import Settings
from stochastiq_api.db import Base, make_engine

config = context.config
target_metadata = Base.metadata

# En ligne de commande (alembic.ini), l'URL vient de DATABASE_URL ; appelé
# depuis l'API, upgrade_database fournit l'URL directement.
URL = Settings().database_url if config.config_file_name else config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    context.configure(url=URL, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(URL)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
