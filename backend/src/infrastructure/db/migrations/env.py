from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Añadir el directorio backend/src al path para imports
sys.path.insert(0, str(Path(__file__).parents[4]))

from src.config import get_settings

# Importar todos los modelos para que Alembic los detecte
from src.infrastructure.db.base import Base
from src.infrastructure.db.models import (  # noqa: F401
    AgentModel,
    FeatureCacheModel,
    MarketDataModel,
    ModelVersionModel,
    PredictionModel,
    RecommendationModel,
)

config = context.config
fileConfig(config.config_file_name)  # type: ignore[arg-type]

# Sobreescribir URL desde pydantic-settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
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
