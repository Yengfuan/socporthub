"""Small Resend HTTP client used by the admin email workflow."""

import logging

import httpx
from fastapi import HTTPException, status

from api.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.resend_api_key or not settings.resend_from_email:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email sending isn't configured yet (RESEND_API_KEY / RESEND_FROM_EMAIL missing)",
        )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={"from": settings.resend_from_email, "to": [to], "subject": subject, "text": body},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("Resend failed for %s", to)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Email provider error") from exc
