"""add Welfare D committee

Revision ID: 0012
Revises: 0011
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO committees (name, color, portfolio, rf_name, rf_email) "
            "SELECT 'Welfare D', '#607D8B', 'welfare', 'Mr Leo', 'leo.lee@nus.edu.sg' "
            "WHERE NOT EXISTS (SELECT 1 FROM committees WHERE name = 'Welfare D')"
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM committees WHERE name = 'Welfare D'")
