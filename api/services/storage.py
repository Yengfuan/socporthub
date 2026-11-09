"""Supabase Storage over its REST API (no SDK): one private bucket for posters and photos.

The browser never gets the service key. It receives short-lived signed URLs instead:
an upload URL so posters go straight to Storage (Vercel caps request bodies at 4.5 MB),
and a download URL so large files never pass through a function response either.

Calls are synchronous (httpx.Client) to match the rest of the sync data layer.
"""

import logging
import re
import uuid
from urllib.parse import quote

import httpx

from api.config import get_settings

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(30.0, connect=10.0)
SIGNED_URL_SECONDS = 10 * 60


class StorageError(RuntimeError):
    pass


def _config() -> tuple[str, str, str]:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_role_key):
        raise StorageError("Supabase Storage is not configured")
    return settings.supabase_url.rstrip("/"), settings.supabase_service_role_key, settings.supabase_storage_bucket


def _headers(key: str, **extra: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}", **extra}


def _quoted(path: str) -> str:
    return "/".join(quote(segment, safe="") for segment in path.split("/"))


def _check(response: httpx.Response, action: str) -> httpx.Response:
    if response.status_code >= 400:
        raise StorageError(f"Storage {action} failed ({response.status_code}): {response.text[:200]}")
    return response


def safe_filename(filename: str | None, fallback: str = "file") -> str:
    """Keep object keys to characters Storage accepts everywhere."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", (filename or "").strip()).strip("-.")
    return (name or fallback)[:100]


def new_path(prefix: str, filename: str | None) -> str:
    return f"{prefix}/{uuid.uuid4().hex}-{safe_filename(filename)}"


def upload(path: str, data: bytes, content_type: str | None) -> None:
    base, key, bucket = _config()
    response = httpx.post(
        f"{base}/storage/v1/object/{bucket}/{_quoted(path)}",
        content=data,
        headers=_headers(key, **{"Content-Type": content_type or "application/octet-stream", "x-upsert": "true"}),
        timeout=TIMEOUT,
    )
    _check(response, "upload")


def download(path: str) -> bytes:
    base, key, bucket = _config()
    response = httpx.get(f"{base}/storage/v1/object/{bucket}/{_quoted(path)}", headers=_headers(key), timeout=TIMEOUT)
    return _check(response, "download").content


def info(path: str) -> dict | None:
    """Size and content type of an uploaded object, or None when it does not exist."""
    base, key, bucket = _config()
    response = httpx.get(f"{base}/storage/v1/object/info/{bucket}/{_quoted(path)}", headers=_headers(key), timeout=TIMEOUT)
    if response.status_code in (400, 404):
        return None
    data = _check(response, "info").json()
    return {"size": data.get("size"), "content_type": data.get("content_type") or data.get("mimetype")}


def delete(*paths: str | None) -> None:
    """Best-effort removal; a leftover object only costs storage, so never raise."""
    targets = [path for path in paths if path]
    if not targets:
        return
    try:
        base, key, bucket = _config()
        response = httpx.request(
            "DELETE", f"{base}/storage/v1/object/{bucket}", json={"prefixes": targets}, headers=_headers(key), timeout=TIMEOUT
        )
        _check(response, "delete")
    except Exception:
        logger.exception("Could not delete storage objects %s", targets)


def signed_download_url(path: str, expires_in: int = SIGNED_URL_SECONDS) -> str:
    base, key, bucket = _config()
    response = httpx.post(
        f"{base}/storage/v1/object/sign/{bucket}/{_quoted(path)}",
        json={"expiresIn": expires_in},
        headers=_headers(key),
        timeout=TIMEOUT,
    )
    signed = _check(response, "sign").json().get("signedURL")
    if not signed:
        raise StorageError("Storage did not return a signed URL")
    return f"{base}/storage/v1{signed}"


def signed_upload_url(path: str) -> str:
    """A one-time URL the browser can PUT the file to (valid for two hours, Supabase's default)."""
    base, key, bucket = _config()
    response = httpx.post(
        f"{base}/storage/v1/object/upload/sign/{bucket}/{_quoted(path)}",
        headers=_headers(key, **{"x-upsert": "true"}),
        timeout=TIMEOUT,
    )
    url = _check(response, "upload sign").json().get("url")
    if not url:
        raise StorageError("Storage did not return an upload URL")
    return f"{base}/storage/v1{url}"
