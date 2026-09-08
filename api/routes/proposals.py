from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import (
    PROPOSAL_STATUS_TRANSITIONS,
    Proposal,
    ProposalStatus,
    User,
    UserRole,
)
from api.schemas import (
    ProposalCreateRequest,
    ProposalOut,
    ProposalStatusCounts,
    ProposalUpdateRequest,
)
from bot.notifications import notify_admins_new_proposal, notify_user_status_change

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _to_out(p: Proposal) -> ProposalOut:
    return ProposalOut(
        id=p.id,
        committee_id=p.committee_id,
        committee_name=p.committee.name,
        submitted_by=p.submitted_by,
        submitter_name=p.submitter.display_name,
        title=p.title,
        description=p.description,
        doc_link=p.doc_link,
        status=p.status,
        event_date=p.event_date,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _visible_query(db: Session, user: User):
    query = db.query(Proposal)
    if user.role != UserRole.admin:
        committee_ids = user.committee_ids
        if not committee_ids:
            return query.filter(False)
        query = query.filter(Proposal.committee_id.in_(committee_ids))
    return query


@router.get("", response_model=list[ProposalOut])
def list_proposals(
    committee_id: int | None = None,
    proposal_status: ProposalStatus | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProposalOut]:
    query = _visible_query(db, user)
    if committee_id is not None:
        query = query.filter(Proposal.committee_id == committee_id)
    if proposal_status is not None:
        query = query.filter(Proposal.status == proposal_status)
    proposals = query.order_by(Proposal.created_at.desc()).all()
    return [_to_out(p) for p in proposals]


@router.get("/summary", response_model=ProposalStatusCounts)
def status_summary(
    committee_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalStatusCounts:
    query = _visible_query(db, user)
    if committee_id is not None:
        query = query.filter(Proposal.committee_id == committee_id)
    counts = ProposalStatusCounts()
    for p in query.all():
        setattr(counts, p.status.value, getattr(counts, p.status.value) + 1)
    return counts


@router.post("", response_model=ProposalOut, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    req: ProposalCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalOut:
    if not user.committee_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You are not assigned to a committee yet")
    # A user may belong to multiple committees; submit under the first for MVP simplicity.
    committee_id = sorted(user.committee_ids)[0]

    proposal = Proposal(
        committee_id=committee_id,
        submitted_by=user.id,
        title=req.title,
        description=req.description,
        doc_link=req.doc_link,
        event_date=req.event_date,
        status=ProposalStatus.needs_action,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    await notify_admins_new_proposal(proposal.title, user.display_name or user.email)

    return _to_out(proposal)


def _get_visible_proposal(db: Session, user: User, proposal_id: int) -> Proposal:
    proposal = _visible_query(db, user).filter(Proposal.id == proposal_id).first()
    if not proposal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return proposal


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalOut:
    return _to_out(_get_visible_proposal(db, user, proposal_id))


@router.patch("/{proposal_id}", response_model=ProposalOut)
async def update_proposal(
    proposal_id: int,
    req: ProposalUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalOut:
    proposal = _get_visible_proposal(db, user, proposal_id)
    is_admin = user.role == UserRole.admin
    is_owner = proposal.submitted_by == user.id

    if req.status is not None:
        if not is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change status")
        allowed = PROPOSAL_STATUS_TRANSITIONS.get(proposal.status, set())
        if req.status not in allowed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot move status from {proposal.status.value} to {req.status.value}",
            )
        proposal.status = req.status

    content_fields = ("title", "description", "doc_link", "event_date")
    if any(getattr(req, f) is not None for f in content_fields):
        if not is_admin and not (is_owner and proposal.status == ProposalStatus.needs_action):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Proposal can only be edited by its owner while in needs_action",
            )
        for field in content_fields:
            value = getattr(req, field)
            if value is not None:
                setattr(proposal, field, value)

    db.commit()
    db.refresh(proposal)

    if req.status is not None:
        await notify_user_status_change(proposal.submitter.telegram_id, proposal.title, proposal.status.value)

    return _to_out(proposal)
