from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user
from api.models import User
from api.schemas import BugReportCreate
from bot.notifications import notify_admins_bug_report


router = APIRouter(prefix="/api/bug-reports", tags=["bug-reports"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def create_bug_report(req: BugReportCreate, user: User = Depends(get_current_user)) -> None:
    message = req.message.strip()
    if not message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Please describe the bug")
    if len(message) > 5000:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Bug report must be 5,000 characters or fewer")
    await notify_admins_bug_report(user, message)
