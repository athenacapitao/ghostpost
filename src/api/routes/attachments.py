"""Attachment download endpoint — lazy download from Gmail."""

import base64
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.api.dependencies import get_current_user
from src.db.models import Attachment, Email
from src.db.session import async_session
from src.gmail.client import GmailClient

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

ATTACHMENT_DIR = "/home/athena/ghostpost/attachments"


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int, _user: str = Depends(get_current_user)
):
    async with async_session() as session:
        att = await session.get(Attachment, attachment_id)
        if not att:
            raise HTTPException(status_code=404, detail="Attachment not found")

        # If already downloaded, serve from disk
        if att.storage_path and os.path.exists(att.storage_path):
            return FileResponse(
                att.storage_path,
                filename=att.filename,
                media_type=att.content_type or "application/octet-stream",
            )

        # Lazy download from Gmail
        if not att.gmail_attachment_id:
            raise HTTPException(status_code=404, detail="No Gmail attachment ID")

        email = await session.get(Email, att.email_id)
        if not email:
            raise HTTPException(status_code=404, detail="Parent email not found")

        client = GmailClient()
        data = await client.get_attachment(email.gmail_id, att.gmail_attachment_id)
        file_data = base64.urlsafe_b64decode(data["data"])

        # Save to disk
        thread_dir = os.path.join(ATTACHMENT_DIR, str(email.thread_id))
        os.makedirs(thread_dir, exist_ok=True)
        safe_name = os.path.basename(att.filename or f"attachment_{att.id}")
        safe_name = safe_name.replace("\x00", "").strip(". ") or f"attachment_{att.id}"
        file_path = os.path.join(thread_dir, safe_name)
        if not os.path.realpath(file_path).startswith(os.path.realpath(thread_dir)):
            raise HTTPException(status_code=400, detail="Invalid attachment filename")
        with open(file_path, "wb") as f:
            f.write(file_data)

        # Update storage path in DB
        att.storage_path = file_path
        session.add(att)
        await session.commit()

        return FileResponse(
            file_path,
            filename=att.filename,
            media_type=att.content_type or "application/octet-stream",
        )
