"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Section 3.2 of SOCIAL-PORT-HUB.md
COMMITTEES = [
    ("Block 2", "#E67C73"),
    ("Block 3", "#F4511E"),
    ("Block 4", "#F6BF26"),
    ("Block 5", "#33B679"),
    ("Block 6", "#039BE5"),
    ("Block 7", "#7986CB"),
    ("Block 8", "#8E24AA"),
    ("Intl Comm", "#616161"),
    ("Soccom", "#D81B60"),
]


def upgrade() -> None:
    committees = op.create_table(
        "committees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="userrole", native_enum=False),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="userstatus", native_enum=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("telegram_id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "user_committees",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), primary_key=True),
    )

    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("committee_id", sa.Integer(), sa.ForeignKey("committees.id"), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("doc_link", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "needs_action", "in_review", "submitted", "finished",
                name="proposalstatus", native_enum=False,
            ),
            nullable=False,
            server_default="needs_action",
        ),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.bulk_insert(
        committees,
        [{"name": name, "color": color} for name, color in COMMITTEES],
    )


def downgrade() -> None:
    op.drop_table("proposals")
    op.drop_table("user_committees")
    op.drop_table("users")
    op.drop_table("committees")
