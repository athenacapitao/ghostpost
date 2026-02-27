"""Async Gmail API client wrapper."""

import asyncio
import logging
from functools import cached_property

from googleapiclient.discovery import build

from src.gmail.auth import get_credentials

logger = logging.getLogger("ghostpost.gmail.client")


class GmailClient:
    """Wraps google-api-python-client with asyncio.to_thread for non-blocking calls."""

    @cached_property
    def _service(self):
        creds = get_credentials()
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _users(self):
        return self._service.users()

    # --- Profile ---

    async def get_profile(self) -> dict:
        return await asyncio.to_thread(
            self._users().getProfile(userId="me").execute
        )

    # --- Messages ---

    async def list_messages(
        self,
        max_results: int = 100,
        page_token: str | None = None,
        q: str | None = None,
    ) -> dict:
        kwargs = {"userId": "me", "maxResults": max_results}
        if page_token:
            kwargs["pageToken"] = page_token
        if q:
            kwargs["q"] = q
        return await asyncio.to_thread(
            self._users().messages().list(**kwargs).execute
        )

    async def get_message(self, msg_id: str, fmt: str = "full") -> dict:
        return await asyncio.to_thread(
            self._users().messages().get(userId="me", id=msg_id, format=fmt).execute
        )

    # --- Threads ---

    async def list_threads(
        self,
        max_results: int = 100,
        page_token: str | None = None,
        q: str | None = None,
    ) -> dict:
        kwargs = {"userId": "me", "maxResults": max_results}
        if page_token:
            kwargs["pageToken"] = page_token
        if q:
            kwargs["q"] = q
        return await asyncio.to_thread(
            self._users().threads().list(**kwargs).execute
        )

    async def get_thread(self, thread_id: str, fmt: str = "full") -> dict:
        return await asyncio.to_thread(
            self._users().threads().get(userId="me", id=thread_id, format=fmt).execute
        )

    # --- Attachments ---

    async def get_attachment(self, msg_id: str, attachment_id: str) -> dict:
        return await asyncio.to_thread(
            self._users()
            .messages()
            .attachments()
            .get(userId="me", messageId=msg_id, id=attachment_id)
            .execute
        )

    # --- Send / Drafts ---

    async def send_message(self, raw_message: str) -> dict:
        """Send a raw RFC 2822 message via Gmail API."""
        import base64
        body = {"raw": base64.urlsafe_b64encode(raw_message.encode()).decode()}
        return await asyncio.to_thread(
            self._users().messages().send(userId="me", body=body).execute
        )

    async def create_gmail_draft(self, raw_message: str, thread_id: str | None = None) -> dict:
        """Create a draft in Gmail."""
        import base64
        message = {"raw": base64.urlsafe_b64encode(raw_message.encode()).decode()}
        if thread_id:
            message["threadId"] = thread_id
        body = {"message": message}
        return await asyncio.to_thread(
            self._users().drafts().create(userId="me", body=body).execute
        )

    async def send_gmail_draft(self, draft_id: str) -> dict:
        """Send an existing Gmail draft."""
        body = {"id": draft_id}
        return await asyncio.to_thread(
            self._users().drafts().send(userId="me", body=body).execute
        )

    async def delete_gmail_draft(self, draft_id: str) -> None:
        """Delete a Gmail draft."""
        await asyncio.to_thread(
            self._users().drafts().delete(userId="me", id=draft_id).execute
        )

    # --- History ---

    async def list_history(
        self,
        start_history_id: str,
        history_types: list[str] | None = None,
        page_token: str | None = None,
    ) -> dict:
        kwargs = {
            "userId": "me",
            "startHistoryId": start_history_id,
        }
        if history_types:
            kwargs["historyTypes"] = history_types
        if page_token:
            kwargs["pageToken"] = page_token
        return await asyncio.to_thread(
            self._users().history().list(**kwargs).execute
        )
