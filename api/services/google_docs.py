"""Download PDFs exported from Google Docs links."""

import re
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status


GOOGLE_DOC_RE = re.compile(r"^/document/d/([A-Za-z0-9_-]+)(?:/|$)")


def proposal_pdf_filename(event_name: str, committee_name: str) -> str:
    """Return a safe, human-readable filename for an emailed proposal PDF."""
    filename = re.sub(r"[^A-Za-z0-9._ -]+", "", f"{event_name}_{committee_name}")
    filename = re.sub(r"\s+", " ", filename).strip(" ._")
    return f"{filename or 'proposal'}.pdf"


async def download_google_doc_pdf(link: str) -> tuple[str, bytes]:
    parsed = urlparse(link)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"docs.google.com", "www.docs.google.com"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The supporting document must be a Google Docs link")

    match = GOOGLE_DOC_RE.match(parsed.path)
    if not match:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The supporting link is not a Google document")

    export_url = f"https://docs.google.com/document/d/{match.group(1)}/export?format=pdf"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(export_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "The Google Doc cannot be accessed. Share it with the system or allow link viewing.",
            ) from exc
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google Docs could not export the document") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Google Docs could not be reached") from exc

    if response.headers.get("content-type", "").split(";", 1)[0].lower() != "application/pdf":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The Google Doc did not return a PDF")
    if len(response.content) > 10 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The generated PDF must be 10 MB or smaller")
    return f"{match.group(1)}.pdf", response.content
