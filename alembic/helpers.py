"""Shared helpers for idempotent Alembic migrations."""
import sqlalchemy as sa
from alembic import op


def has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))
