"""add Telegram usernames to users

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_username", sa.String(length=33), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_unique_constraint("uq_users_telegram_username", "users", ["telegram_username"])


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_users_telegram_username", "users", type_="unique")
    op.drop_column("users", "telegram_username")
