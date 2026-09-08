from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_admin
from api.database import get_db
from api.models import Committee, User, UserCommittee, UserStatus
from api.schemas import UserOut, UserUpdateRequest
from bot.notifications import notify_user_registration_approved, notify_user_registration_rejected

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _to_user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.committees = [m.committee for m in user.committee_memberships]
    return out


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[UserOut]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_to_user_out(u) for u in users]


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> UserOut:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    previous_status = user.status

    if req.status is not None:
        user.status = req.status

    if req.committee_ids is not None:
        found = db.query(Committee).filter(Committee.id.in_(req.committee_ids)).all()
        if len(found) != len(set(req.committee_ids)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown committee_id in list")
        db.query(UserCommittee).filter(UserCommittee.user_id == user.id).delete()
        for committee_id in req.committee_ids:
            db.add(UserCommittee(user_id=user.id, committee_id=committee_id))

    db.commit()
    db.refresh(user)

    if previous_status != UserStatus.approved and user.status == UserStatus.approved:
        await notify_user_registration_approved(user.telegram_id)
    elif previous_status != UserStatus.rejected and user.status == UserStatus.rejected:
        await notify_user_registration_rejected(user.telegram_id)

    return _to_user_out(user)
