"""fix_pool_bets_timestamp_server_defaults

Add server_default=CURRENT_TIMESTAMP to pool_bets.created_at and
pool_bets.updated_at. The original migration (c18060e1d4ec) created the
table without DEFAULT clauses, so raw INSERTs that omit these columns fail
with NOT NULL constraint violations on SQLite.

Revision ID: a3b1c2d4e5f6
Revises: f448b649718b
Create Date: 2026-02-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = 'a3b1c2d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f448b649718b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server_default (CURRENT_TIMESTAMP) to pool_bets timestamp columns.

    SQLite batch mode rebuilds the table, which lets us set server_default
    on columns that were created without one.
    """
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )


def downgrade() -> None:
    """Remove server_default from pool_bets timestamp columns."""
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.alter_column(
            'created_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            'updated_at',
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=None,
        )
