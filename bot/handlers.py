"""Handles incoming Telegram webhook updates (commands only, no WebApp interaction —
that goes through the REST API instead)."""

import logging

from api.config import get_settings
from api.database import SessionLocal
from api.models import DisposableRequest, Proposal, ProposalStatus, Reminder, ReminderTargetType, User, UserRole
from api.services.telegram import send_message, webapp_open_markup

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "<b>Social Port Hub</b>\n\n"
    "/start — Open the app\n"
    "/status — Show your proposal status\n"
    "/remind <message> — Nudge the admin\n"
    "/help — Show this message\n\n"
    "Use the app to submit event proposals, track their status, and manage your "
    "committee's activity."
)


async def handle_update(update: dict) -> None:
    message = update.get("message")
    if not message:
        return  # ignore non-message updates (e.g. callback_query) for now

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None:
        return

    command, _, argument = text.partition(" ")
    if command == "/start":
        await _handle_start(chat_id)
    elif command == "/help":
        await send_message(chat_id, HELP_TEXT)
    elif command == "/status":
        await _handle_status(chat_id)
    elif command == "/remind":
        await _handle_remind(chat_id, argument.strip())
    elif command == "/pending":
        await _handle_pending(chat_id)
    elif command == "/approve":
        await _handle_approve(chat_id, argument.strip())


async def _handle_start(chat_id: int) -> None:
    settings = get_settings()
    if settings.telegram_webapp_url:
        await send_message(
            chat_id,
            "Use the button below to acces the Social Port Hub!\n\n💡 Tip: Pin this message so you can easily open the app anytime.",
            reply_markup=webapp_open_markup(settings.telegram_webapp_url),
        )
    else:
        await send_message(chat_id, "Welcome to Social Port Hub! The app link isn't configured yet.")


def _user(db, chat_id: int):
    return db.query(User).filter(User.telegram_id == chat_id).first()


async def _handle_status(chat_id: int) -> None:
    with SessionLocal() as db:
        user = _user(db, chat_id)
        if not user or user.status.value != "approved":
            await send_message(chat_id, "You don't have an approved Social Port Hub account yet.")
            return
        query = db.query(Proposal)
        if user.role != UserRole.admin:
            query = query.filter(Proposal.committee_id.in_(user.committee_ids))
        proposals = query.order_by(Proposal.updated_at.desc()).limit(10).all()
        if not proposals:
            await send_message(chat_id, "You have no visible proposals yet.")
            return
        lines = [f"• {p.title}: {p.status.value}" for p in proposals]
    await send_message(chat_id, "<b>Your proposal status</b>\n" + "\n".join(lines))


async def _handle_remind(chat_id: int, message: str) -> None:
    if not message:
        await send_message(chat_id, "Usage: /remind Please review my proposal")
        return
    with SessionLocal() as db:
        user = _user(db, chat_id)
        if not user or user.status.value != "approved":
            await send_message(chat_id, "You need an approved account to send reminders.")
            return
        reminder = Reminder(from_user=user.id, message=message, target_type=ReminderTargetType.general)
        db.add(reminder)
        db.commit()
        sender = user.display_name or user.email
    from bot.notifications import notify_admins_reminder
    await notify_admins_reminder(sender, message)
    await send_message(chat_id, "Your reminder was sent to the admin.")


async def _handle_pending(chat_id: int) -> None:
    with SessionLocal() as db:
        user = _user(db, chat_id)
        if not user or user.role != UserRole.admin or user.status.value != "approved":
            return
        proposals = db.query(Proposal).filter(Proposal.status == ProposalStatus.needs_action).all()
        disposables = db.query(DisposableRequest).filter(DisposableRequest.approved.is_(False)).all()
    lines = [f"• Proposal #{p.id}: {p.title}" for p in proposals]
    lines += [f"• Disposables #{d.id}: {d.proposal.title}" for d in disposables]
    await send_message(chat_id, "<b>Pending items</b>\n" + ("\n".join(lines) if lines else "Nothing pending."))


async def _handle_approve(chat_id: int, argument: str) -> None:
    try:
        disposable_id = int(argument)
    except ValueError:
        await send_message(chat_id, "Usage: /approve <disposable id>")
        return
    with SessionLocal() as db:
        user = _user(db, chat_id)
        disposable = db.get(DisposableRequest, disposable_id) if user and user.role == UserRole.admin else None
        if not disposable:
            await send_message(chat_id, "Disposable request not found.")
            return
        disposable.approved = True
        db.commit()
        recipient_id = disposable.requester.telegram_id
        proposal_title = disposable.proposal.title
        collection_date = disposable.collection_date.isoformat()
    from bot.notifications import notify_user_disposable_approved
    await notify_user_disposable_approved(recipient_id, proposal_title, collection_date)
    await send_message(chat_id, f"Disposable request #{disposable_id} approved.")
