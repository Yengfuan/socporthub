"""own database-backed calendar, drop committees.google_color_id

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.drop_column("committees", "google_color_id")


def downgrade() -> None:
    op.add_column(
        "committees",
        sa.Column("google_color_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.drop_table("calendar_events")
