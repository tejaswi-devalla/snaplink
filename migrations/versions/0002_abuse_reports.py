"""Add abuse reports for moderation workflow.

Revision ID: 0002_abuse_reports
Revises: 0001_initial
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_abuse_reports"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "abuse_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("details", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["code"], ["short_links.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_abuse_reports_status_created_at",
        "abuse_reports",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_abuse_reports_status_created_at", table_name="abuse_reports")
    op.drop_table("abuse_reports")
