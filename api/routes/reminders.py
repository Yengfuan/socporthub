from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import DisposableRequest, Proposal, Reminder, ReminderTargetType, User, UserRole
from api.schemas import ReminderCreate, ReminderOut, ReminderUnreadCount
from bot.notifications import notify_admins_reminder

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


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
        if not proposal or (user.role != UserRole.admin and proposal.committee_id not in user.committee_ids):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if req.target_type == ReminderTargetType.disposable:
        disposable = db.get(DisposableRequest, req.target_id) if req.target_id else None
        if not disposable or (user.role != UserRole.admin and disposable.requested_by != user.id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Disposable request not found")

    reminder = Reminder(
        from_user=user.id, message=req.message.strip(), target_type=req.target_type, target_id=req.target_id
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    await notify_admins_reminder(user.display_name or user.email, reminder.message)
    return _out(reminder)


@router.get("", response_model=list[ReminderOut])
def list_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ReminderOut]:
    query = db.query(Reminder)
    if user.role != UserRole.admin:
        query = query.filter(Reminder.from_user == user.id)
    return [_out(r) for r in query.order_by(Reminder.created_at.desc()).all()]


@router.get("/unread-count", response_model=ReminderUnreadCount)
def unread_count(db: Session = Depends(get_db), admin: User = Depends(get_current_user)) -> ReminderUnreadCount:
    if admin.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return ReminderUnreadCount(count=db.query(Reminder).filter(Reminder.is_read.is_(False)).count())


@router.patch("/{reminder_id}/read", response_model=ReminderOut)
def mark_read(reminder_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_user)) -> ReminderOut:
    if admin.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    reminder = db.get(Reminder, reminder_id)
    if not reminder:
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
