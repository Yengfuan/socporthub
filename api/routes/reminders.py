from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import DisposableRequest, Proposal, Reminder, ReminderTargetType, User, UserRole
from api.portfolio import admin_can_access_committee, committee_portfolio
from api.schemas import ReminderCreate, ReminderOut, ReminderUnreadCount
from bot.notifications import notify_admins_reminder

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _admin_can_see_reminder(db: Session, reminder: Reminder, admin: User) -> bool:
    if admin.role != UserRole.admin:
        return False
    if reminder.target_type == ReminderTargetType.proposal and reminder.target_id:
        proposal = db.get(Proposal, reminder.target_id)
        return bool(proposal and admin_can_access_committee(admin, proposal.committee))
    if reminder.target_type == ReminderTargetType.disposable and reminder.target_id:
        disposable = db.get(DisposableRequest, reminder.target_id)
        return bool(disposable and admin_can_access_committee(admin, disposable.proposal.committee))
    return any(admin_can_access_committee(admin, m.committee) for m in reminder.sender.committee_memberships)


def _out(reminder: Reminder) -> ReminderOut:
    return ReminderOut(
        id=reminder.id,
        from_user=reminder.from_user,
        sender_name=reminder.sender.display_name or reminder.sender.email,
        message=reminder.message,
        target_type=reminder.target_type,
        target_id=reminder.target_id,
        is_read=reminder.is_read,
        created_at=reminder.created_at,
    )


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def create_reminder(req: ReminderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ReminderOut:
    if not req.message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reminder message cannot be empty")
    if req.target_type == ReminderTargetType.general and req.target_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "General reminders cannot have a target")
    if req.target_type == ReminderTargetType.proposal:
        proposal = db.get(Proposal, req.target_id) if req.target_id else None
        if not proposal or (
            user.role != UserRole.admin
            and proposal.committee_id not in user.committee_ids
        ) or (
            user.role == UserRole.admin
            and not admin_can_access_committee(user, proposal.committee)
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if req.target_type == ReminderTargetType.disposable:
        disposable = db.get(DisposableRequest, req.target_id) if req.target_id else None
        if not disposable or (
            user.role != UserRole.admin and disposable.requested_by != user.id
        ) or (
            user.role == UserRole.admin
            and not admin_can_access_committee(user, disposable.proposal.committee)
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Disposable request not found")

    reminder = Reminder(
        from_user=user.id, message=req.message.strip(), target_type=req.target_type, target_id=req.target_id
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    portfolio = None
    if req.target_type == ReminderTargetType.proposal and proposal:
        portfolio = committee_portfolio(proposal.committee)
    elif user.committee_memberships:
        portfolio = committee_portfolio(user.committee_memberships[0].committee)
    await notify_admins_reminder(user.display_name or user.email, reminder.message, portfolio)
    return _out(reminder)


@router.get("", response_model=list[ReminderOut])
def list_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ReminderOut]:
    reminders = db.query(Reminder).order_by(Reminder.created_at.desc()).all()
    if user.role != UserRole.admin:
        reminders = [r for r in reminders if r.from_user == user.id]
    else:
        reminders = [r for r in reminders if _admin_can_see_reminder(db, r, user)]
    return [_out(r) for r in reminders]


@router.get("/unread-count", response_model=ReminderUnreadCount)
def unread_count(db: Session = Depends(get_db), admin: User = Depends(get_current_user)) -> ReminderUnreadCount:
    if admin.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    reminders = db.query(Reminder).filter(Reminder.is_read.is_(False)).all()
    return ReminderUnreadCount(count=sum(_admin_can_see_reminder(db, r, admin) for r in reminders))


@router.patch("/{reminder_id}/read", response_model=ReminderOut)
def mark_read(reminder_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_user)) -> ReminderOut:
    if admin.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found")
    if not _admin_can_see_reminder(db, reminder, admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found")
    reminder.is_read = True
    db.commit()
    db.refresh(reminder)
    return _out(reminder)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(reminder_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_user)) -> None:
    if admin.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found")
    db.delete(reminder)
    db.commit()
