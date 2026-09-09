"""Telegram WebApp initData validation.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
"""

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.config import get_settings
from api.database import get_db
from api.models import Portfolio, User, UserRole, UserStatus

INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60


@dataclass
class TelegramIdentity:
    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


def parse_and_verify_init_data(init_data: str, bot_token: str) -> TelegramIdentity:
    """Verify the HMAC signature of Telegram WebApp initData and return the identity.

    Raises HTTPException(401) if the data is missing, malformed, unsigned, expired, or
    the signature doesn't match.
    """
    if not init_data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing initData")

    pairs = parse_qsl(init_data, strict_parsing=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData missing hash")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid initData signature")

    auth_date = data.get("auth_date")
    if auth_date and time.time() - int(auth_date) > INIT_DATA_MAX_AGE_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")

    user_raw = data.get("user")
    if not user_raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData missing user")

    user_json = json.loads(user_raw)
    return TelegramIdentity(
        telegram_id=user_json["id"],
        first_name=user_json.get("first_name"),
        last_name=user_json.get("last_name"),
        username=user_json.get("username"),
    )


def verify_init_data(init_data: str) -> TelegramIdentity:
    settings = get_settings()
    if settings.environment == "development" and not settings.telegram_bot_token:
        # Local dev without a bot token configured: allow a synthetic identity so the
        # webapp is testable outside Telegram. Never enabled when a token is set.
        raw = dict(parse_qsl(init_data))
        dev_id = raw.get("dev_telegram_id")
        if dev_id:
            return TelegramIdentity(telegram_id=int(dev_id))
    return parse_and_verify_init_data(init_data, settings.telegram_bot_token)


def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: resolve an approved User from the initData header.

    The webapp attaches `Telegram.WebApp.initData` as the `X-Telegram-Init-Data` header
    on every request. Raises 401/403/404 for invalid, unregistered, or unapproved users.
    """
    identity = verify_init_data(x_telegram_init_data)
    user = db.query(User).filter(User.telegram_id == identity.telegram_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not registered")
    # Admin IDs are configuration-driven. Promote an already-registered user when
    # their Telegram ID is added to Railway, rather than requiring re-registration.
    if identity.telegram_id in get_settings().all_admin_telegram_id_set and user.role != UserRole.admin:
        user.role = UserRole.admin
        user.status = UserStatus.approved
        db.commit()
        db.refresh(user)
    if user.status != UserStatus.approved:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"User is {user.status.value}")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def admin_portfolio(user: User) -> Portfolio:
    settings = get_settings()
    if user.telegram_id in settings.welfare_admin_telegram_id_set:
        return Portfolio.welfare
    return Portfolio.social
