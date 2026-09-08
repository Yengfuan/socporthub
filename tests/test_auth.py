import hashlib
import hmac
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from api.auth import parse_and_verify_init_data


def build_init_data(bot_token: str, user: dict, auth_date: int | None = None) -> str:
    import json

    data = {
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AA1234",
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_valid_init_data_is_accepted():
    init_data = build_init_data("dummy-token", {"id": 42, "first_name": "Ada"})
    identity = parse_and_verify_init_data(init_data, "dummy-token")
    assert identity.telegram_id == 42
    assert identity.first_name == "Ada"


def test_tampered_hash_is_rejected():
    init_data = build_init_data("dummy-token", {"id": 42, "first_name": "Ada"})
    tampered = init_data.replace("Ada", "Eve")
    with pytest.raises(HTTPException) as exc_info:
        parse_and_verify_init_data(tampered, "dummy-token")
    assert exc_info.value.status_code == 401


def test_wrong_bot_token_is_rejected():
    init_data = build_init_data("dummy-token", {"id": 42, "first_name": "Ada"})
    with pytest.raises(HTTPException) as exc_info:
        parse_and_verify_init_data(init_data, "other-token")
    assert exc_info.value.status_code == 401


def test_expired_init_data_is_rejected():
    stale_date = int(time.time()) - 25 * 60 * 60
    init_data = build_init_data("dummy-token", {"id": 42, "first_name": "Ada"}, auth_date=stale_date)
    with pytest.raises(HTTPException) as exc_info:
        parse_and_verify_init_data(init_data, "dummy-token")
    assert exc_info.value.status_code == 401


def test_missing_hash_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        parse_and_verify_init_data("user=%7B%22id%22%3A1%7D", "dummy-token")
    assert exc_info.value.status_code == 401
