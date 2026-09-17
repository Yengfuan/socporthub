"""add grading evidence done timestamp

Revision ID: 0022
Revises: 0021
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("proposal_gradings", sa.Column("evidence_done_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("proposal_gradings", "evidence_done_at")
