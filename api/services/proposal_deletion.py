from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.models import (
    CalendarEvent,
    DeletionRequestStatus,
    DisposableRequest,
    EmailDraft,
    GradingNotification,
    Proposal,
    ProposalComment,
    ProposalCommentRead,
    ProposalDeletionRequest,
    ProposalGrading,
    ProposalStatusHistory,
    User,
)


def delete_proposal(db: Session, proposal: Proposal, *, decided_by: User) -> None:
    """Hard-deletes a proposal and everything attached to it, in the caller's
    transaction (the caller commits). Any pending deletion request for it is closed as
    approved, since the outcome it asked for has happened.

    Not touched: the linked Google Doc and any Drive folder, which live outside this
    database."""
    pid = proposal.id

    # Closed first, and kept: the request row is the record of why it was deleted.
    now = datetime.now(timezone.utc)
    for request in db.query(ProposalDeletionRequest).filter(
        ProposalDeletionRequest.proposal_id == pid,
        ProposalDeletionRequest.status == DeletionRequestStatus.pending,
    ):
        request.status = DeletionRequestStatus.approved
        request.decided_by = decided_by.id
        request.decided_at = now

    # Replies point at their parent comment, so detach them before deleting comments.
    db.query(ProposalComment).filter(ProposalComment.proposal_id == pid).update(
        {ProposalComment.reply_to_comment_id: None}, synchronize_session=False
    )
    for model in (
        ProposalComment,
        ProposalCommentRead,
        ProposalStatusHistory,
        ProposalGrading,
        GradingNotification,
        DisposableRequest,  # approved or not
        EmailDraft,
        CalendarEvent,  # the entry created when the proposal finished
    ):
        db.query(model).filter(model.proposal_id == pid).delete(synchronize_session=False)

    db.expire_all()
    db.delete(db.get(Proposal, pid))
    db.flush()
