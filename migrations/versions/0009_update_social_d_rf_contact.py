"""set Social D RF contact details

Revision ID: 0009
Revises: 0008
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE committees SET rf_name = 'Ms Linda', rf_email = 'lindacheng@nus.edu.sg' "
        "WHERE name = 'Social D'"
    )


def downgrade() -> None:
    op.execute("UPDATE committees SET rf_name = NULL, rf_email = NULL WHERE name = 'Social D'")
