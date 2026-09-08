from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import Committee, User
from api.schemas import CommitteeOut

router = APIRouter(prefix="/api/committees", tags=["committees"])


@router.get("", response_model=list[CommitteeOut])
def list_committees(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CommitteeOut]:
    return db.query(Committee).order_by(Committee.name).all()
