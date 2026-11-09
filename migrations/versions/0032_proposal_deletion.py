"""proposal deletion requests; calendar events remember the proposal they came from

Revision ID: 0032
Revises: 0031
"""

from alembic import op
import sqlalchemy as sa


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_deletion_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Plain integer, not a foreign key: the proposal is hard-deleted on approval.
        sa.Column("proposal_id", sa.Integer(), nullable=False, index=True),
        sa.Column("proposal_title", sa.String(255), nullable=False),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE proposal_deletion_requests ENABLE ROW LEVEL SECURITY")

    with op.batch_alter_table("calendar_events") as batch:
        batch.add_column(sa.Column("proposal_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_calendar_events_proposal_id", "proposals", ["proposal_id"], ["id"])

    # Link existing calendar entries to the finished proposal they were created from.
    # Best effort: matched by committee, title and date (the only link there was).
    op.execute(
        """
        UPDATE calendar_events SET proposal_id = (
            SELECT p.id FROM proposals AS p
            WHERE p.committee_id = calendar_events.committee_id
              AND p.title = calendar_events.title
              AND p.event_date = calendar_events.event_date
              AND p.status IN ('finished', 'grading', 'final')
            ORDER BY p.id LIMIT 1
        )
        WHERE is_blockout = false
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("calendar_events") as batch:
        batch.drop_constraint("fk_calendar_events_proposal_id", type_="foreignkey")
        batch.drop_column("proposal_id")
    op.drop_table("proposal_deletion_requests")
