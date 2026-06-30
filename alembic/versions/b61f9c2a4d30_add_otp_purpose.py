"""add otp purpose

Revision ID: b61f9c2a4d30
Revises: a20e1322a627
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

import sys
from pathlib import Path

from alembic import op
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import has_column  # noqa: E402


revision: str = "b61f9c2a4d30"
down_revision: Union[str, None] = "a20e1322a627"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if has_column("otp_records", "purpose"):
        return

    op.add_column(
        "otp_records",
        sa.Column(
            "purpose",
            sa.String(length=30),
            nullable=False,
            server_default="registration",
        ),
    )
    op.create_index(op.f("ix_otp_records_purpose"), "otp_records", ["purpose"], unique=False)
    op.alter_column("otp_records", "purpose", server_default=None)


def downgrade() -> None:
    if not has_column("otp_records", "purpose"):
        return

    op.drop_index(op.f("ix_otp_records_purpose"), table_name="otp_records")
    op.drop_column("otp_records", "purpose")
