"""allow proposal comments to reply to other comments

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("proposal_comments", sa.Column("reply_to_comment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_proposal_comments_reply_to", "proposal_comments", "proposal_comments", ["reply_to_comment_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_proposal_comments_reply_to", "proposal_comments", type_="foreignkey")
    op.drop_column("proposal_comments", "reply_to_comment_id")
