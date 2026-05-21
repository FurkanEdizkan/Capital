"""Alembic migration environment.

The database URL comes from the engine settings (config.py), so migrations and
the running app always agree on the target database. `target_metadata` is
`SQLModel.metadata`; later phases import their model modules below so
`alembic revision --autogenerate` can see every table.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from appsettings import models as _settings_models  # noqa: F401 — register tables
from auth import models as _auth_models  # noqa: F401 — register tables on metadata
from config import settings
from db import SQLModel
from marketdata import models as _md_models  # noqa: F401 — register tables on metadata
from trading import models as _trading_models  # noqa: F401 — register tables on metadata

# Model modules are imported above so their tables register on
# SQLModel.metadata and `alembic revision --autogenerate` can see them.

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live DB connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
