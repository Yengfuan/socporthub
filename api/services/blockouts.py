from sqlalchemy.orm import Session

from api.models import CalendarEvent, Proposal, ProposalStatus

# Once a proposal has finished (or moved on to grading), its date is history and a
# later block-out should not flag it.
_CLASH_EXEMPT_STATUSES = (ProposalStatus.finished, ProposalStatus.grading, ProposalStatus.final)


def blockout_clash(db: Session, proposal: Proposal) -> str | None:
    """Returns a warning when another committee holds a block-out on the proposal's
    event date, else None. Computed on read (never stored), so it appears if a
    block-out is added later and clears when one is removed. The owning committee is
    exempt."""
    if proposal.event_date is None or proposal.status in _CLASH_EXEMPT_STATUSES:
        return None
    clash = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.is_blockout.is_(True),
            CalendarEvent.event_date == proposal.event_date,
            CalendarEvent.committee_id != proposal.committee_id,
        )
        .order_by(CalendarEvent.id)
        .first()
    )
    if clash is None:
        return None
    return f"{clash.committee.name} has a block-out on this date ({clash.title})"
