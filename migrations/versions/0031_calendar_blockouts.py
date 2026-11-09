"""calendar events can be flagged as block-out dates

Revision ID: 0031
Revises: 0030
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No new table, so no row-level-security step. Existing rows become normal events.
    op.add_column(
        "calendar_events",
        sa.Column("is_blockout", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_column("is_blockout")
