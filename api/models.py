import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class UserStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ProposalStatus(str, enum.Enum):
    needs_action = "needs_action"
    in_review = "in_review"
    submitted = "submitted"
    finished = "finished"


# Server-side allowed forward transitions for proposal status.
PROPOSAL_STATUS_TRANSITIONS: dict[ProposalStatus, set[ProposalStatus]] = {
    ProposalStatus.needs_action: {ProposalStatus.in_review},
    ProposalStatus.in_review: {ProposalStatus.submitted, ProposalStatus.needs_action},
    ProposalStatus.submitted: {ProposalStatus.finished},
    ProposalStatus.finished: set(),
}


class Committee(Base):
    __tablename__ = "committees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)

    memberships: Mapped[list["UserCommittee"]] = relationship(back_populates="committee")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="committee")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="committee")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), default=UserRole.user)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, native_enum=False), default=UserStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    committee_memberships: Mapped[list["UserCommittee"]] = relationship(back_populates="user")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="submitter")

    @property
    def committee_ids(self) -> set[int]:
        return {m.committee_id for m in self.committee_memberships}


class UserCommittee(Base):
    __tablename__ = "user_committees"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), primary_key=True)

    user: Mapped["User"] = relationship(back_populates="committee_memberships")
    committee: Mapped["Committee"] = relationship(back_populates="memberships")


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), nullable=False)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    doc_link: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, native_enum=False), default=ProposalStatus.needs_action
    )
    event_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    committee: Mapped["Committee"] = relationship(back_populates="proposals")
    submitter: Mapped["User"] = relationship(back_populates="proposals")
    comments: Mapped[list["ProposalComment"]] = relationship(
        back_populates="proposal", order_by="ProposalComment.created_at"
    )
    disposable_request: Mapped["DisposableRequest | None"] = relationship(back_populates="proposal")


class ProposalComment(Base):
    __tablename__ = "proposal_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proposal: Mapped["Proposal"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship()


class DisposableRequest(Base):
    __tablename__ = "disposable_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), unique=True, nullable=False)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    plates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cups: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    forks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spoons: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    collection_date: Mapped[date] = mapped_column(Date, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proposal: Mapped["Proposal"] = relationship(back_populates="disposable_request")
    requester: Mapped["User"] = relationship()


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    committee: Mapped["Committee"] = relationship(back_populates="calendar_events")
    creator: Mapped["User"] = relationship()
