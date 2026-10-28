"""Create short_links table.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "short_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("management_token_hash", sa.String(length=64), nullable=False),
        sa.Column("click_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_clicked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_short_links_code"),
    )
    op.create_index("ix_short_links_created_at", "short_links", ["created_at"], unique=False)
    op.create_index("ix_short_links_expires_at", "short_links", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_short_links_expires_at", table_name="short_links")
    op.drop_index("ix_short_links_created_at", table_name="short_links")
    op.drop_table("short_links")
