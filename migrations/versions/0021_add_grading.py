"""Proposal grading, evidence folders and durable reminders.

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    # Existing status/category columns are non-native enums (VARCHAR).
    op.add_column("proposals", sa.Column("drive_folder_id", sa.String(255)))
    op.add_column("proposals", sa.Column("drive_pdf_id", sa.String(255)))
    op.add_column("proposals", sa.Column("drive_ready", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("proposals", sa.Column("drive_error", sa.Text()))
    op.create_table(
        "proposal_gradings",
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("proposals.id"), primary_key=True),
        sa.Column("started_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("admin_data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("user_submitted_at", sa.DateTime(timezone=True)),
        sa.Column("admin_submitted_at", sa.DateTime(timezone=True)),
        sa.Column("admin_author_id", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "grading_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("milestone", sa.String(32), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("proposal_id", "milestone", "telegram_id"),
    )


def downgrade():
    op.drop_table("grading_notifications")
    op.drop_table("proposal_gradings")
    for column in ("drive_error", "drive_ready", "drive_pdf_id", "drive_folder_id"):
        op.drop_column("proposals", column)
