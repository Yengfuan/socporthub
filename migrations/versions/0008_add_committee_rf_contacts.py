"""add RF contact details to committees

Revision ID: 0008
Revises: 0007
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RF_CONTACTS = {
    "Block 2": ("Prof Mornin", "morning@nus.edu.sg"),
    "Block 3": ("Ms Linda", "lindacheng@nus.edu.sg"),
    "Block 4": ("Prof Ezra", "ezra.chiam@nus.edu.sg"),
    "Block 5": ("Prof Donn", "donn@nus.edu.sg"),
    "Block 6": ("Prof Lee", "honsing@nus.edu.sg"),
    "Block 7": ("Mr Leo", "leo.lee@nus.edu.sg"),
    "Block 8": ("Mr Leo", "leo.lee@nus.edu.sg"),
    "Intl Comm": ("Ms Linda", "lindacheng@nus.edu.sg"),
    "Soccom": ("Ms Linda", "lindacheng@nus.edu.sg"),
}


def upgrade() -> None:
    op.add_column("committees", sa.Column("rf_name", sa.String(length=255), nullable=True))
    op.add_column("committees", sa.Column("rf_email", sa.String(length=255), nullable=True))
    committees = sa.table(
        "committees",
        sa.column("name", sa.String),
        sa.column("rf_name", sa.String),
        sa.column("rf_email", sa.String),
    )
    for name, (rf_name, rf_email) in RF_CONTACTS.items():
        op.execute(
            committees.update()
            .where(committees.c.name == name)
            .values(rf_name=rf_name, rf_email=rf_email)
        )
    # Social D is seeded by migration 0002, but its RF contact has not been
    # supplied yet. Keep these columns nullable until that contact is provided.


def downgrade() -> None:
    op.drop_column("committees", "rf_email")
    op.drop_column("committees", "rf_name")
