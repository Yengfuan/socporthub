"""proposal comments, disposable requests, committee google_color_id

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Google Calendar's fixed event color palette (colorId -> background hex).
# https://developers.google.com/calendar/api/v3/reference/colors
GOOGLE_EVENT_COLORS = {
    1: "a4bdfc",  # Lavender
    2: "7ae7bf",  # Sage
    3: "dbadff",  # Grape
    4: "ff887c",  # Flamingo
    5: "fbd75b",  # Banana
    6: "ffb878",  # Tangerine
    7: "46d6db",  # Peacock
    8: "e1e1e1",  # Graphite
    9: "5484ed",  # Blueberry
    10: "51b749",  # Basil
    11: "dc2127",  # Tomato
}


def _nearest_color_id(hex_color: str) -> int:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

    def distance(candidate_hex: str) -> int:
        cr, cg, cb = int(candidate_hex[0:2], 16), int(candidate_hex[2:4], 16), int(candidate_hex[4:6], 16)
        return (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2

    return min(GOOGLE_EVENT_COLORS, key=lambda cid: distance(GOOGLE_EVENT_COLORS[cid]))


def upgrade() -> None:
    op.add_column(
        "committees",
        sa.Column("google_color_id", sa.Integer(), nullable=False, server_default="1"),
    )

    bind = op.get_bind()
    committees_table = sa.table(
        "committees", sa.column("id", sa.Integer), sa.column("color", sa.String)
    )
    for committee_id, color in bind.execute(sa.select(committees_table.c.id, committees_table.c.color)):
        bind.execute(
            sa.text("UPDATE committees SET google_color_id = :cid WHERE id = :id"),
            {"cid": _nearest_color_id(color), "id": committee_id},
        )

    op.create_table(
        "proposal_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "disposable_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposal_id", sa.Integer(), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cups", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spoons", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collection_date", sa.Date(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("proposal_id"),
    )


def downgrade() -> None:
    op.drop_table("disposable_requests")
    op.drop_table("proposal_comments")
    op.drop_column("committees", "google_color_id")
