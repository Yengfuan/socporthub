"""object-storage paths for posters and return photos; once-a-day scheduled job receipts

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
    op.add_column("proposals", sa.Column("poster_storage_path", sa.String(512), nullable=True))
    op.add_column("borrow_requests", sa.Column("return_proof_storage_path", sa.String(512), nullable=True))
    op.create_table(
        "scheduled_job_runs",
        sa.Column("job", sa.String(64), primary_key=True),
        sa.Column("last_run_on", sa.Date(), nullable=True),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.scheduled_job_runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("scheduled_job_runs")
    with op.batch_alter_table("borrow_requests") as batch:
        batch.drop_column("return_proof_storage_path")
    with op.batch_alter_table("proposals") as batch:
        batch.drop_column("poster_storage_path")
