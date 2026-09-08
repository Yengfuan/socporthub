"""add Social D committee

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMMITTEE_NAME = "Social D"
COMMITTEE_COLOR = "#00897B"

committees_table = sa.table(
    "committees",
    sa.column("name", sa.String),
    sa.column("color", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(committees_table, [{"name": COMMITTEE_NAME, "color": COMMITTEE_COLOR}])


def downgrade() -> None:
    op.execute(committees_table.delete().where(committees_table.c.name == COMMITTEE_NAME))
