"""add proposal categories, posters, blast messages, and disposable times

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("category", sa.String(length=20), nullable=False, server_default="pantry_cleaning"))
    op.add_column("proposals", sa.Column("blast_message", sa.Text(), nullable=True))
    op.add_column("proposals", sa.Column("poster_filename", sa.String(length=255), nullable=True))
    op.add_column("proposals", sa.Column("poster_content_type", sa.String(length=100), nullable=True))
    op.add_column("proposals", sa.Column("poster_data", sa.LargeBinary(), nullable=True))
    op.add_column("disposable_requests", sa.Column("collection_time", sa.Time(), nullable=True))
    op.alter_column("proposals", "category", server_default=None)


def downgrade() -> None:
    op.drop_column("disposable_requests", "collection_time")
    op.drop_column("proposals", "poster_data")
    op.drop_column("proposals", "poster_content_type")
    op.drop_column("proposals", "poster_filename")
    op.drop_column("proposals", "blast_message")
    op.drop_column("proposals", "category")
