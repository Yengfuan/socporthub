"""Outbound Telegram notification templates, one function per trigger in the spec's
notification flow table. Routes call these instead of building message text inline."""

from html import escape

from api.config import get_settings
from api.services.telegram import send_message


async def notify_admins_new_registration(display_name: str | None, email: str) -> None:
    settings = get_settings()
    text = f"\U0001f4dd New registration pending approval: <b>{display_name or email}</b> ({email})"
    for admin_id in settings.admin_telegram_id_set:
        await send_message(admin_id, text)


async def notify_user_registration_approved(telegram_id: int) -> None:
    await send_message(
        telegram_id,
        "✅ Your access to Social Port Hub has been approved. Open the app from the menu button to get started.",
    )


async def notify_user_registration_rejected(telegram_id: int) -> None:
    await send_message(
        telegram_id,
        "Your Social Port Hub registration was not approved. Contact the Social Director for details.",
    )


async def notify_admins_new_proposal(proposal_title: str, submitter_name: str) -> None:
    settings = get_settings()
    text = f"\U0001f4cb New proposal <b>{proposal_title}</b> submitted by {submitter_name}"
    for admin_id in settings.admin_telegram_id_set:
        await send_message(admin_id, text)


async def notify_user_status_change(
    telegram_id: int, proposal_title: str, new_status: str, comment: str | None = None
) -> None:
    text = f"\U0001f4e2 Your proposal <b>{proposal_title}</b> status changed to <b>{new_status}</b>"
    if comment:
        text += f"\n\n\U0001f4ac {comment}"
    await send_message(telegram_id, text)


async def notify_admins_new_disposable_request(proposal_title: str, requester_name: str) -> None:
    settings = get_settings()
    text = f"\U0001f37d New disposables request for <b>{proposal_title}</b> from {requester_name}"
    for admin_id in settings.admin_telegram_id_set:
        await send_message(admin_id, text)


async def notify_user_disposable_approved(telegram_id: int, proposal_title: str, collection_date: str) -> None:
    await send_message(
        telegram_id,
        f"✅ Disposables approved for <b>{proposal_title}</b> — collect on {collection_date}.",
    )


async def notify_user_email_sent(telegram_id: int, proposal_title: str) -> None:
    await send_message(
        telegram_id,
        f"✅ Your proposal <b>{proposal_title}</b> has been submitted. The confirmation email is on its way.",
    )


async def notify_admins_reminder(sender_name: str, message: str) -> None:
    settings = get_settings()
    text = f"🔔 Reminder from <b>{escape(sender_name)}</b>\n\n{escape(message)}"
    for admin_id in settings.admin_telegram_id_set:
        await send_message(admin_id, text)
