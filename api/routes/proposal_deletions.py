from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import (
    Committee,
    DeletionRequestStatus,
    Proposal,
    ProposalDeletionRequest,
    User,
    UserRole,
)
from api.portfolio import admin_can_access_committee, admin_committee_filter, can_manage_proposal
from api.schemas import DeletionRequestCreate, DeletionRequestDecision, DeletionRequestOut
from api.services.proposal_deletion import delete_proposal

router = APIRouter(prefix="/api/proposal-deletions", tags=["proposal-deletions"])


def _to_out(r: ProposalDeletionRequest) -> DeletionRequestOut:
    return DeletionRequestOut(
        id=r.id,
        proposal_id=r.proposal_id,
        proposal_title=r.proposal_title,
        committee_name=r.committee.name,
        requester_name=r.requester.display_name,
        reason=r.reason,
        status=r.status.value,
        decision_note=r.decision_note,
        created_at=r.created_at,
        decided_at=r.decided_at,
    )


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")


@router.get("", response_model=list[DeletionRequestOut])
def list_requests(
    proposal_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DeletionRequestOut]:
    """Admins: pending requests inside their portfolio (the dashboard notice).
    Everyone else: requests they made or that were made for their committees,
    whatever the status."""
    query = db.query(ProposalDeletionRequest)
    if proposal_id is not None:
        query = query.filter(ProposalDeletionRequest.proposal_id == proposal_id)
    if user.role == UserRole.admin:
        query = (
            query.join(ProposalDeletionRequest.committee)
            .filter(ProposalDeletionRequest.status == DeletionRequestStatus.pending)
            .filter(admin_committee_filter(user))
        )
    else:
        query = query.filter(
            or_(
                ProposalDeletionRequest.requested_by == user.id,
                ProposalDeletionRequest.committee_id.in_(user.committee_ids or {-1}),
            )
        )
    return [_to_out(r) for r in query.order_by(ProposalDeletionRequest.created_at.desc()).all()]


@router.post("", response_model=DeletionRequestOut, status_code=status.HTTP_201_CREATED)
def create_request(
    req: DeletionRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeletionRequestOut:
    if user.role == UserRole.admin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Admins delete proposals directly; no request needed")
    reason = req.reason.strip()
    if not reason:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A reason is required")
    # Any member of the proposal's committee can ask for it to be deleted.
    proposal = db.get(Proposal, req.proposal_id)
    if not proposal or not can_manage_proposal(user, proposal):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    already_pending = (
        db.query(ProposalDeletionRequest)
        .filter(
            ProposalDeletionRequest.proposal_id == proposal.id,
            ProposalDeletionRequest.status == DeletionRequestStatus.pending,
        )
        .first()
    )
    if already_pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "A deletion request is already waiting for admin approval")

    request = ProposalDeletionRequest(
        proposal_id=proposal.id,
        proposal_title=proposal.title,
        committee_id=proposal.committee_id,
        requested_by=user.id,
        reason=reason,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return _to_out(request)


def _get_pending(db: Session, admin: User, request_id: int) -> ProposalDeletionRequest:
    _require_admin(admin)
    request = db.get(ProposalDeletionRequest, request_id)
    if not request:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if not admin_can_access_committee(admin, db.get(Committee, request.committee_id)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request is outside your portfolio")
    if request.status != DeletionRequestStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "This request has already been decided")
    return request


@router.post("/{request_id}/approve", response_model=DeletionRequestOut)
def approve_request(
    request_id: int,
    req: DeletionRequestDecision | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
) -> DeletionRequestOut:
    request = _get_pending(db, admin, request_id)
    proposal = db.get(Proposal, request.proposal_id)
    if proposal:
        # Also closes this request as approved (and any other pending one).
        delete_proposal(db, proposal, decided_by=admin)
    else:  # proposal already gone; just close the request
        request.status = DeletionRequestStatus.approved
        request.decided_by = admin.id
        request.decided_at = datetime.now(timezone.utc)
    request = db.get(ProposalDeletionRequest, request_id)
    if req and req.note:
        request.decision_note = req.note
    db.commit()
    db.refresh(request)
    return _to_out(request)


@router.post("/{request_id}/reject", response_model=DeletionRequestOut)
def reject_request(
    request_id: int,
    req: DeletionRequestDecision | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_user),
) -> DeletionRequestOut:
    request = _get_pending(db, admin, request_id)
    request.status = DeletionRequestStatus.rejected
    request.decided_by = admin.id
    request.decided_at = datetime.now(timezone.utc)
    request.decision_note = req.note if req else None
    db.commit()
    db.refresh(request)
    return _to_out(request)
