"""Signed, short-lived links for downloading proposal documents externally."""

import hashlib
import hmac
import time
from urllib.parse import quote

from fastapi import HTTPException, status

from api.config import get_settings

DOCUMENT_LINK_TTL_SECONDS = 7 * 24 * 60 * 60


def create_document_token(proposal_id: int) -> str:
    expires = int(time.time()) + DOCUMENT_LINK_TTL_SECONDS
    payload = f"{proposal_id}.{expires}"
    signature = hmac.new(
        get_settings().secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_document_token(token: str, proposal_id: int) -> None:
    try:
        token_proposal_id, expires, signature = token.split(".", 2)
        payload = f"{token_proposal_id}.{expires}"
        valid = (
            int(token_proposal_id) == proposal_id
            and int(expires) >= int(time.time())
            and hmac.compare_digest(
                signature,
                hmac.new(get_settings().secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest(),
            )
        )
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This document link is invalid or expired")


def document_download_url(proposal_id: int) -> str:
    base_url = get_settings().telegram_webapp_url.rstrip("/")
    if not base_url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "TELEGRAM_WEBAPP_URL is required for large PDF links")
    return f"{base_url}/api/proposals/{proposal_id}/document?token={quote(create_document_token(proposal_id))}"
