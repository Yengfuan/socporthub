"""Small Resend HTTP client used by the admin email workflow."""

import logging
import base64

import httpx
from fastapi import HTTPException, status

from api.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(
    *, to: str, subject: str, body: str, cc: str | list[str] | None = None, attachment: tuple[str, bytes] | None = None
) -> None:
    settings = get_settings()
    if not settings.resend_api_key or not settings.resend_from_email:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email sending isn't configured yet (RESEND_API_KEY / RESEND_FROM_EMAIL missing)",
        )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {"from": settings.resend_from_email, "to": [to], "subject": subject, "text": body}
            if cc:
                payload["cc"] = [cc] if isinstance(cc, str) else cc
            if attachment:
                filename, content = attachment
                payload["attachments"] = [{"filename": filename, "content": base64.b64encode(content).decode("ascii")}]
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Resend's response body explains exactly why the send was rejected (unverified
        # sender domain, recipient restrictions on an unverified account, etc.) — the
        # generic exception message alone doesn't include it.
        logger.error("Resend rejected email to %s: %s", to, exc.response.text)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Email provider error: {exc.response.text}") from exc
    except httpx.HTTPError as exc:
        logger.exception("Resend request failed for %s", to)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Email provider error") from exc
