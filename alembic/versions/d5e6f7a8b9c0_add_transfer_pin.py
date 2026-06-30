"""add transfer pin hash to users

Revision ID: d5e6f7a8b9c0
Revises: c4f8a1b2e3d0
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

import sys
from pathlib import Path

from alembic import op
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import has_column  # noqa: E402


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4f8a1b2e3d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_column("users", "transfer_pin_hash"):
        return

    op.add_column("users", sa.Column("transfer_pin_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    if not has_column("users", "transfer_pin_hash"):
        return

    op.drop_column("users", "transfer_pin_hash")
