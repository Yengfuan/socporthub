"""Idempotent shared-drive evidence folders."""
import asyncio
import json
import logging

import httpx
from sqlalchemy.orm import Session

from api.config import get_settings
from api.models import Portfolio, Proposal
from api.portfolio import committee_portfolio
from api.services.google_docs import download_google_doc_pdf, proposal_pdf_filename

logger = logging.getLogger(__name__)
BASE = "https://www.googleapis.com/drive/v3"


def folder_url(proposal):
    if not proposal.drive_ready or not proposal.drive_folder_id:
        return None
    if proposal.drive_folder_id.startswith("preview-"):
        return None
    return f"https://drive.google.com/drive/folders/{proposal.drive_folder_id}"


def _access_token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    settings = get_settings()
    options = {"scopes": ["https://www.googleapis.com/auth/drive.file"]}
    if settings.google_service_account_json:
        credentials = service_account.Credentials.from_service_account_info(json.loads(settings.google_service_account_json), **options)
    else:
        credentials = service_account.Credentials.from_service_account_file(settings.google_service_account_file, **options)
    credentials.refresh(Request())
    return credentials.token


async def provision_evidence(db: Session, proposal_id: int):
    settings = get_settings()
    if not settings.grading_enabled or settings.google_drive_mode == "disabled":
        return
    proposal = db.query(Proposal).filter_by(id=proposal_id).with_for_update().one()
    if settings.google_drive_mode != "live":
        return
    try:
        parent = (settings.google_drive_welfare_parent_folder_id if committee_portfolio(proposal.committee) == Portfolio.welfare else settings.google_drive_social_parent_folder_id) or settings.google_drive_parent_folder_id
        if not parent:
            raise ValueError("Drive parent folder is not configured")
        token = await asyncio.to_thread(_access_token)
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=45) as client:
            if not proposal.drive_folder_id:
                response = await client.get(f"{BASE}/files/generateIds", params={"count": 2, "space": "drive", "type": "files"})
                response.raise_for_status()
                proposal.drive_folder_id, proposal.drive_pdf_id = response.json()["ids"]
                # Reserve IDs before external creation, so a crash/retry reuses them.
                db.commit()
            if not proposal.drive_ready:
                response = await client.post(f"{BASE}/files", params={"supportsAllDrives": "true"}, json={
                    "id": proposal.drive_folder_id,
                    "name": f"{proposal.committee.name}-{proposal.title}",
                    "mimeType": "application/vnd.google-apps.folder", "parents": [parent],
                    "appProperties": {"proposal_id": str(proposal.id)},
                })
                if response.status_code != 409:  # Same reserved ID already created.
                    response.raise_for_status()
                proposal.drive_ready = True
                db.commit()
            # Grant only the submitter upload access. Admin access is inherited
            # from the configured portfolio parent, never public link sharing.
            permissions = await client.get(f"{BASE}/files/{proposal.drive_folder_id}/permissions", params={"supportsAllDrives": "true", "fields": "permissions(id,emailAddress,role)"})
            permissions.raise_for_status()
            if not any(p.get("emailAddress", "").lower() == proposal.submitter.email.lower() and p["role"] in ("writer", "organizer", "fileOrganizer", "owner") for p in permissions.json().get("permissions", [])):
                response = await client.post(f"{BASE}/files/{proposal.drive_folder_id}/permissions", params={"supportsAllDrives": "true", "sendNotificationEmail": "false"}, json={"type": "user", "role": "writer", "emailAddress": proposal.submitter.email})
                response.raise_for_status()
            if proposal.doc_link and proposal.drive_pdf_id:
                response = await client.get(f"{BASE}/files/{proposal.drive_pdf_id}", params={"supportsAllDrives": "true", "fields": "id"})
                if response.status_code == 404:
                    _, pdf = await download_google_doc_pdf(proposal.doc_link)
                    metadata = {"id": proposal.drive_pdf_id, "name": proposal_pdf_filename(proposal.title, proposal.committee.name), "parents": [proposal.drive_folder_id]}
                    boundary = "rh_proposal_pdf_boundary"
                    data = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n--{boundary}\r\nContent-Type: application/pdf\r\n\r\n").encode() + pdf + f"\r\n--{boundary}--\r\n".encode()
                    response = await client.post("https://www.googleapis.com/upload/drive/v3/files", params={"uploadType": "multipart", "supportsAllDrives": "true"}, headers={"Content-Type": f"multipart/related; boundary={boundary}"}, content=data)
                    if response.status_code != 409:
                        response.raise_for_status()
                else:
                    response.raise_for_status()
        proposal.drive_error = None
        db.commit()
    except Exception:
        db.rollback()
        # Don't expose credentials/provider responses to users. Keep the folder
        # usable if only PDF export or sharing failed, and retry in the scheduler.
        proposal = db.get(Proposal, proposal_id)
        proposal.drive_error = "Evidence setup is incomplete. Folder access or PDF copying will be retried."
        db.commit()
        logger.warning("Evidence setup failed for proposal %s", proposal_id)
