"""rename the Bakers And Cooks committee

Revision ID: 0013
Revises: 0012
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE committees SET name = 'BakeRHs and Cooks' WHERE name = 'Bakers And Cooks'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE committees SET name = 'Bakers And Cooks' WHERE name = 'BakeRHs and Cooks'"
    )
