from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import Committee, User, UserRole
from api.portfolio import admin_committee_filter
from api.schemas import CommitteeOut

router = APIRouter(prefix="/api/committees", tags=["committees"])


@router.get("", response_model=list[CommitteeOut])
def list_committees(
    all_committees: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CommitteeOut]:
    query = db.query(Committee)
    if user.role == UserRole.admin and not all_committees:
        query = query.filter(admin_committee_filter(user))
    return query.order_by(Committee.name).all()
