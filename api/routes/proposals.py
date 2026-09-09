from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import (
    PROPOSAL_STATUS_TRANSITIONS,
    CalendarEvent,
    Proposal, EmailDraft,
    ProposalComment,
    ProposalCategory, ProposalStatus,
    User,
    UserRole,
)
from api.schemas import (
    ProposalCommentCreate,
    ProposalCommentOut,
    ProposalCreateRequest,
    ProposalOut,
    ProposalStatusCounts,
    ProposalUpdateRequest,
)
from bot.notifications import (
    notify_admins_new_proposal,
    notify_user_status_change,
)
from api.routes.email import _committee_ccs, _generated, _without_links
from api.services.google_docs import download_google_doc_pdf, proposal_pdf_filename
from api.services.resend_email import send_email

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


def _to_out(p: Proposal) -> ProposalOut:
    return ProposalOut(
        id=p.id,
        committee_id=p.committee_id,
        committee_name=p.committee.name,
        submitted_by=p.submitted_by,
        submitter_name=p.submitter.display_name,
        title=p.title,
        category=p.category,
        description=p.description,
        doc_link=p.doc_link,
        blast_message=p.blast_message,
        poster_filename=p.poster_filename,
        poster_content_type=p.poster_content_type,
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


def _validate_category_requirements(
    category: ProposalCategory,
    *,
    event_date,
    doc_link: str | None,
    blast_message: str | None,
    poster_data: bytes | None,
    check_poster: bool,
) -> None:
    """Shared field requirements for a proposal about to become in_review.

    check_poster is False at creation time — a poster upload is a separate follow-up
    call after the proposal exists, so it can't be checked yet there. The frontend
    still enforces it client-side before allowing that follow-up call to be skipped.
    """
    if category in (ProposalCategory.event, ProposalCategory.initiative, ProposalCategory.pantry_cleaning) and not event_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An event date is required for this category")
    if check_poster and category in (ProposalCategory.event, ProposalCategory.initiative, ProposalCategory.merch) and not poster_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A poster is required for this category")
    if category in (ProposalCategory.event, ProposalCategory.merch) and not doc_link:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A link or PDF URL is required for this category")
    if category in (ProposalCategory.event, ProposalCategory.initiative) and not blast_message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A blast message is required for this category")


@router.post("", response_model=ProposalOut, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    req: ProposalCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalOut:
    if not user.committee_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You are not assigned to a committee yet")
    if not req.save_draft:
        _validate_category_requirements(
            req.category,
            event_date=req.event_date,
            doc_link=req.doc_link,
            blast_message=req.blast_message,
            poster_data=None,
            check_poster=False,
        )
    # A user may belong to multiple committees; submit under the first for MVP simplicity.
    committee_id = sorted(user.committee_ids)[0]

    proposal = Proposal(
        committee_id=committee_id,
        submitted_by=user.id,
        title=req.title,
        category=req.category,
        description=req.description,
        doc_link=req.doc_link,
        blast_message=req.blast_message,
        event_date=req.event_date,
        status=ProposalStatus.draft if req.save_draft else ProposalStatus.in_review,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    if not req.save_draft:
        await notify_admins_new_proposal(proposal.title, user.display_name or user.email)

    return _to_out(proposal)


def get_visible_proposal(db: Session, user: User, proposal_id: int) -> Proposal:
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
    return _to_out(get_visible_proposal(db, user, proposal_id))


@router.patch("/{proposal_id}", response_model=ProposalOut)
async def update_proposal(
    proposal_id: int,
    req: ProposalUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalOut:
    proposal = get_visible_proposal(db, user, proposal_id)
    is_admin = user.role == UserRole.admin
    is_owner = proposal.submitted_by == user.id

    if req.status is not None:
        # Owner can submit a draft, and can resubmit after being sent back to
        # needs_action — both land on in_review. Every other transition is admin-only.
        owner_can_submit = (
            is_owner
            and proposal.status in (ProposalStatus.draft, ProposalStatus.needs_action)
            and req.status == ProposalStatus.in_review
        )
        if not is_admin and not owner_can_submit:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can change status")
        allowed = PROPOSAL_STATUS_TRANSITIONS.get(proposal.status, set())
        if req.status not in allowed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot move status from {proposal.status.value} to {req.status.value}",
            )
        was_awaiting_review = proposal.status in (ProposalStatus.draft, ProposalStatus.needs_action)
        proposal.status = req.status

    content_fields = ("category", "title", "description", "doc_link", "blast_message", "event_date")
    # Use model_fields_set (not "is not None") so a client can explicitly clear a
    # nullable field — e.g. {"event_date": null} — by including the key in the payload.
    # Omitting the key entirely means "leave this field alone".
    provided_content_fields = req.model_fields_set & set(content_fields)
    if provided_content_fields:
        if not is_admin and not (is_owner and proposal.status in (ProposalStatus.draft, ProposalStatus.needs_action)):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Proposal can only be edited by its owner while in needs_action",
            )
        if "title" in provided_content_fields and req.title is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "title cannot be cleared")
        for field in provided_content_fields:
            setattr(proposal, field, getattr(req, field))

    if req.status == ProposalStatus.in_review:
        _validate_category_requirements(
            proposal.category,
            event_date=proposal.event_date,
            doc_link=proposal.doc_link,
            blast_message=proposal.blast_message,
            poster_data=proposal.poster_data,
            check_poster=True,
        )

    if req.comment:
        db.add(ProposalComment(proposal_id=proposal.id, author_id=user.id, body=req.comment))

    if req.status == ProposalStatus.finished and proposal.event_date is not None:
        # Finished proposals graduate from a "proposal date" marker to a real, shared
        # calendar entry — visible with the committee color and in the .ics feed.
        db.add(
            CalendarEvent(
                committee_id=proposal.committee_id,
                created_by=user.id,
                title=proposal.title,
                description=proposal.description,
                event_date=proposal.event_date,
            )
        )

    # Approval has an external side effect (PDF export + email). Keep the status
    # change pending until that side effect succeeds, so a failed email does not
    # falsely tell the admin that the proposal was submitted.
    sends_confirmation_email = req.status == ProposalStatus.submitted and proposal.category == ProposalCategory.event
    if not sends_confirmation_email:
        db.commit()
        db.refresh(proposal)

    if req.status == ProposalStatus.in_review and was_awaiting_review:
        # A fresh draft submission or a resubmission after needs_action both mean
        # "there's something for an admin to review now" — same signal as a new proposal.
        await notify_admins_new_proposal(proposal.title, proposal.submitter.display_name or proposal.submitter.email)

    if sends_confirmation_email:
        draft = db.query(EmailDraft).filter(EmailDraft.proposal_id == proposal.id).first()
        if draft:
            subject, body = draft.subject, draft.body
        else:
            subject, body = _generated(proposal)
        attachment = None
        if proposal.doc_link:
            _, pdf = await download_google_doc_pdf(proposal.doc_link)
            attachment = (proposal_pdf_filename(proposal.title, proposal.committee.name), pdf)
        await send_email(
            to=proposal.submitter.email,
            subject=_without_links(subject),
            body=_without_links(body),
            cc=_committee_ccs(proposal),
            attachment=attachment,
        )
        db.commit()
        db.refresh(proposal)

    if req.status is not None:
        await notify_user_status_change(
            proposal.submitter.telegram_id, proposal.title, proposal.status.value, req.comment
        )

    return _to_out(proposal)


@router.post("/{proposal_id}/poster", response_model=ProposalOut)
async def upload_poster(
    proposal_id: int,
    poster: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalOut:
    proposal = get_visible_proposal(db, user, proposal_id)
    if proposal.submitted_by != user.id or proposal.status not in (ProposalStatus.draft, ProposalStatus.needs_action):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can upload a poster while editing")
    if proposal.category not in (ProposalCategory.event, ProposalCategory.initiative, ProposalCategory.merch):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Posters are only used for Event, Initiative, and Merch proposals")
    if poster.content_type not in {"image/jpeg", "image/png", "image/webp", "application/pdf"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Poster must be a PDF, PNG, JPG, or WEBP file")
    data = await poster.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Poster must be 10 MB or smaller")
    proposal.poster_filename = poster.filename or "poster"
    proposal.poster_content_type = poster.content_type
    proposal.poster_data = data
    db.commit()
    db.refresh(proposal)
    return _to_out(proposal)


@router.get("/{proposal_id}/poster")
def download_poster(proposal_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    proposal = get_visible_proposal(db, user, proposal_id)
    if not proposal.poster_data or not proposal.poster_content_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Poster not found")
    return Response(
        content=proposal.poster_data,
        media_type=proposal.poster_content_type,
        headers={"Content-Disposition": f'inline; filename="{proposal.poster_filename or "poster"}"'},
    )


def _comment_to_out(c: ProposalComment) -> ProposalCommentOut:
    out = ProposalCommentOut.model_validate(c)
    out.author_name = c.author.display_name or c.author.email
    return out


@router.get("/{proposal_id}/comments", response_model=list[ProposalCommentOut])
def list_comments(
    proposal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProposalCommentOut]:
    proposal = get_visible_proposal(db, user, proposal_id)
    return [_comment_to_out(c) for c in proposal.comments]


@router.post("/{proposal_id}/comments", response_model=ProposalCommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    proposal_id: int,
    req: ProposalCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProposalCommentOut:
    proposal = get_visible_proposal(db, user, proposal_id)
    comment = ProposalComment(proposal_id=proposal.id, author_id=user.id, body=req.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_to_out(comment)
