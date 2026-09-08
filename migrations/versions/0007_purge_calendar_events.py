"""purge calendar_events for v1 release

One-time data cleanup: wipes every row in calendar_events regardless of which
committee/status/date it came from, so the calendar starts blank for the v1 release.
This does not touch proposals, disposables, or any other table — only synced calendar
entries (routes/calendar.py; auto-created when a proposal is marked finished, or added
directly through the Calendar tab).

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM calendar_events")


def downgrade() -> None:
    pass  # purged rows aren't recoverable; nothing to reverse
