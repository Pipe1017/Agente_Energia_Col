"""add_unique_constraint_ts_agent

Revision ID: bd630a1c569f
Revises: ab8330540d1b
Create Date: 2026-03-04 01:19:59.028244

Reemplaza el índice regular ix_market_data_agent_ts por un índice único
NULLS NOT DISTINCT (PostgreSQL 15+) para soportar UPSERT idempotente
en market_data por (timestamp, agent_sic_code) donde agent_sic_code puede ser NULL.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'bd630a1c569f'
down_revision: Union[str, None] = 'ab8330540d1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Eliminar el índice regular anterior (puede no existir si ya se eliminó manualmente)
    op.execute("DROP INDEX IF EXISTS ix_market_data_agent_ts")

    # Crear índice único con NULLS NOT DISTINCT para que NULL == NULL
    # Esto permite ON CONFLICT (timestamp, agent_sic_code) con valores NULL
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_market_data_ts_agent
        ON market_data (timestamp, agent_sic_code)
        NULLS NOT DISTINCT
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_market_data_ts_agent")
    op.create_index("ix_market_data_agent_ts", "market_data", ["agent_sic_code", "timestamp"])
