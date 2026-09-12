from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import Committee, User, UserRole
from api.portfolio import admin_committee_filter
from api.schemas import CommitteeFormOut, CommitteeOut
from api.services.google_forms import configured_forms

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


@router.get("/forms", response_model=list[CommitteeFormOut])
def list_committee_forms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CommitteeFormOut]:
    """List configured form destinations, including external committees.

    A form destination is deliberately independent from the app's internal
    committee membership. For example, SFI can receive requests without being
    an internal Social Port Hub committee.
    """
    internal_committees = {c.name: c.id for c in db.query(Committee).all()}
    return [
        CommitteeFormOut(
            form_key=name,
            committee_id=internal_committees.get(name),
            committee_name=name,
            **form,
        )
        for name, form in configured_forms()
    ]
