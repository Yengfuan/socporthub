from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from api.models import ProposalStatus, UserRole, UserStatus


# --- Auth ---


class ValidateResponse(BaseModel):
    registered: bool
    user: "UserOut | None" = None


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None


# --- Users ---


class CommitteeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    email: str
    display_name: str | None
    role: UserRole
    status: UserStatus
    created_at: datetime
    committees: list[CommitteeOut] = []


class UserUpdateRequest(BaseModel):
    status: UserStatus | None = None
    committee_ids: list[int] | None = None


# --- Proposals ---


class ProposalCreateRequest(BaseModel):
    title: str
    description: str | None = None
    doc_link: str | None = None
    event_date: date | None = None


class ProposalUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    doc_link: str | None = None
    event_date: date | None = None
    status: ProposalStatus | None = None


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    committee_id: int
    committee_name: str
    submitted_by: int
    submitter_name: str | None
    title: str
    description: str | None
    doc_link: str | None
    status: ProposalStatus
    event_date: date | None
    created_at: datetime
    updated_at: datetime


class ProposalStatusCounts(BaseModel):
    needs_action: int = 0
    in_review: int = 0
    submitted: int = 0
    finished: int = 0
