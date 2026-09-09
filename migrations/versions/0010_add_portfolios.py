"""assign committees to Social and Welfare portfolios

Revision ID: 0010
Revises: 0009
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WELFARE_COMMITTEES = [
    "Welfare Comm", "HeaRHtfelt", "Green Commm", "Bakers And Cooks",
    "Children", "Pioneers", "Special Projects", "Special Needs",
]


def upgrade() -> None:
    op.add_column("committees", sa.Column("portfolio", sa.String(length=20), nullable=True))
    op.execute("UPDATE committees SET portfolio = 'social' WHERE portfolio IS NULL")
    for name in WELFARE_COMMITTEES:
        op.execute(
            sa.text(
                "INSERT INTO committees (name, color, portfolio) "
                "SELECT :name, '#607D8B', 'welfare' "
                "WHERE NOT EXISTS (SELECT 1 FROM committees WHERE name = :name)"
            ).bindparams(name=name)
        )
        op.execute(sa.text("UPDATE committees SET portfolio = 'welfare' WHERE name = :name").bindparams(name=name))


def downgrade() -> None:
    op.execute("DELETE FROM committees WHERE portfolio = 'welfare'")
    op.drop_column("committees", "portfolio")
