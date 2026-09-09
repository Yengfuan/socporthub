"""set the shared Welfare RF contact

Revision ID: 0011
Revises: 0010
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE committees SET rf_name = 'Mr Leo', rf_email = 'leo.lee@nus.edu.sg' "
        "WHERE portfolio = 'welfare'"
    )


def downgrade() -> None:
    op.execute("UPDATE committees SET rf_name = NULL, rf_email = NULL WHERE portfolio = 'welfare'")
