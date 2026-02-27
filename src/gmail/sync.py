"""Email sync engine — full and incremental sync from Gmail."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.events import publish_event
from src.db.models import Attachment, Contact, Email, Thread
from src.db.session import async_session
from src.engine.context_writer import _append_changelog
from src.gmail.client import GmailClient
from src.gmail.parser import parse_message

logger = logging.getLogger("ghostpost.gmail.sync")


class SyncEngine:
    def __init__(self):
        self.client = GmailClient()
        self.status: dict = {
            "running": False,
            "last_sync": None,
            "last_history_id": None,
            "emails_synced": 0,
            "threads_synced": 0,
            "contacts_synced": 0,
            "error": None,
        }

    async def full_sync(self) -> dict:
        """Paginate all threads from Gmail, store everything. Idempotent."""
        logger.info("Starting full sync")
        self.status["running"] = True
        self.status["error"] = None
        stats = {"threads": 0, "emails": 0, "contacts": 0, "attachments": 0}

        try:
            # Get current history ID for future incremental syncs
            profile = await self.client.get_profile()
            self.status["last_history_id"] = profile.get("historyId")

            # Paginate through all threads
            page_token = None
            thread_ids = []
            while True:
                result = await self.client.list_threads(
                    max_results=100, page_token=page_token
                )
                for t in result.get("threads", []):
                    thread_ids.append(t["id"])
                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            logger.info(f"Found {len(thread_ids)} threads to sync")

            # Process each thread
            for gmail_thread_id in thread_ids:
                thread_data = await self.client.get_thread(gmail_thread_id)
                thread_stats = await self._process_thread(thread_data)
                stats["threads"] += 1
                stats["emails"] += thread_stats["emails"]
                stats["contacts"] += thread_stats["contacts"]
                stats["attachments"] += thread_stats["attachments"]

            self.status["last_sync"] = datetime.now(timezone.utc).isoformat()
            self.status["emails_synced"] = stats["emails"]
            self.status["threads_synced"] = stats["threads"]
            self.status["contacts_synced"] = stats["contacts"]
            logger.info(f"Full sync complete: {stats}")
            await publish_event("sync_complete", {"mode": "full", **stats})
            _append_changelog(
                "sync_complete",
                f"{stats['emails']} new emails, {stats['threads']} threads updated",
            )
            return stats

        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            self.status["error"] = str(e)
            raise
        finally:
            self.status["running"] = False

    async def incremental_sync(self) -> dict:
        """Use Gmail history API for delta changes since last sync."""
        if not self.status["last_history_id"]:
            logger.info("No history ID — falling back to full sync")
            return await self.full_sync()

        logger.info(f"Starting incremental sync from historyId={self.status['last_history_id']}")
        self.status["running"] = True
        self.status["error"] = None
        stats = {"threads": 0, "emails": 0, "contacts": 0, "attachments": 0}

        try:
            # Collect all changed message IDs from history
            changed_thread_ids = set()
            page_token = None
            while True:
                try:
                    result = await self.client.list_history(
                        start_history_id=self.status["last_history_id"],
                        history_types=["messageAdded", "messageDeleted"],
                        page_token=page_token,
                    )
                except Exception as e:
                    if "404" in str(e) or "historyId" in str(e).lower():
                        logger.warning("History ID expired, falling back to full sync")
                        return await self.full_sync()
                    raise

                for record in result.get("history", []):
                    for msg in record.get("messagesAdded", []):
                        changed_thread_ids.add(msg["message"]["threadId"])

                if "historyId" in result:
                    self.status["last_history_id"] = result["historyId"]

                page_token = result.get("nextPageToken")
                if not page_token:
                    break

            logger.info(f"Incremental sync: {len(changed_thread_ids)} threads changed")

            for gmail_thread_id in changed_thread_ids:
                thread_data = await self.client.get_thread(gmail_thread_id)
                thread_stats = await self._process_thread(thread_data)
                stats["threads"] += 1
                stats["emails"] += thread_stats["emails"]
                stats["contacts"] += thread_stats["contacts"]
                stats["attachments"] += thread_stats["attachments"]

            self.status["last_sync"] = datetime.now(timezone.utc).isoformat()
            self.status["emails_synced"] += stats["emails"]
            self.status["threads_synced"] += stats["threads"]
            logger.info(f"Incremental sync complete: {stats}")
            await publish_event("sync_complete", {"mode": "incremental", **stats})
            _append_changelog(
                "sync_complete",
                f"{stats['emails']} new emails, {stats['threads']} threads updated",
            )
            return stats

        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            self.status["error"] = str(e)
            raise
        finally:
            self.status["running"] = False

    async def _process_thread(self, thread_data: dict) -> dict:
        """Process a single Gmail thread — upsert thread, emails, contacts, attachments."""
        stats = {"emails": 0, "contacts": 0, "attachments": 0}
        gmail_thread_id = thread_data["id"]
        messages = thread_data.get("messages", [])
        if not messages:
            return stats

        # Parse all messages first
        parsed = [parse_message(m) for m in messages]
        subject = parsed[0].get("subject") or "(no subject)"
        last_msg = parsed[-1]

        now = datetime.now(timezone.utc)

        async with async_session() as session:
            async with session.begin():
                # Upsert thread
                thread_stmt = pg_insert(Thread).values(
                    gmail_thread_id=gmail_thread_id,
                    subject=subject,
                    state="NEW",
                    created_at=now,
                    last_activity_at=last_msg.get("date") or now,
                ).on_conflict_do_update(
                    index_elements=["gmail_thread_id"],
                    set_={
                        "last_activity_at": last_msg.get("date") or now,
                        "updated_at": now,
                    },
                )
                await session.execute(thread_stmt)

                # Get the thread ID
                result = await session.execute(
                    select(Thread.id).where(Thread.gmail_thread_id == gmail_thread_id)
                )
                thread_id = result.scalar_one()

                # Process each message
                for p in parsed:
                    # Upsert email
                    email_stmt = pg_insert(Email).values(
                        gmail_id=p["gmail_id"],
                        thread_id=thread_id,
                        message_id=p["message_id"],
                        from_address=p["from_address"],
                        to_addresses=p["to_addresses"],
                        cc=p["cc"],
                        bcc=p["bcc"],
                        subject=p["subject"],
                        body_plain=p["body_plain"],
                        body_html=p["body_html"],
                        date=p["date"],
                        received_at=p["received_at"],
                        headers=p["headers"],
                        attachment_metadata=p["attachments"] if p["attachments"] else None,
                        is_read=p["is_read"],
                        is_sent=p["is_sent"],
                        is_draft=p["is_draft"],
                    ).on_conflict_do_nothing(index_elements=["gmail_id"])
                    result = await session.execute(email_stmt)
                    if result.rowcount > 0:
                        stats["emails"] += 1
                        await publish_event("new_email", {
                            "gmail_id": p["gmail_id"],
                            "subject": p["subject"],
                            "from": p["from_address"],
                            "thread_gmail_id": gmail_thread_id,
                        })

                        # Get the email ID for attachments
                        email_result = await session.execute(
                            select(Email.id).where(Email.gmail_id == p["gmail_id"])
                        )
                        email_id = email_result.scalar_one()

                        # Insert attachments
                        for att in p["attachments"]:
                            att_stmt = pg_insert(Attachment).values(
                                email_id=email_id,
                                filename=att["filename"],
                                content_type=att["content_type"],
                                size=att["size"],
                                gmail_attachment_id=att["gmail_attachment_id"],
                            ).on_conflict_do_nothing()
                            await session.execute(att_stmt)
                            stats["attachments"] += 1

                    # Upsert contact from sender
                    stats["contacts"] += await self._upsert_contact(
                        session, p["from_name"], p["from_address"], p["date"]
                    )

        # Post-processing: injection scanning + auto state transitions for new emails
        if stats["emails"] > 0:
            await self._post_process_thread(thread_id, stats["emails"])

        return stats

    async def _post_process_thread(self, thread_id: int, new_email_count: int) -> None:
        """Run injection scanning and auto state transitions on new emails in a thread."""
        try:
            # Auto-transition: if thread was WAITING_REPLY/FOLLOW_UP, move to ACTIVE
            from src.engine.state_machine import auto_transition_on_receive
            await auto_transition_on_receive(thread_id)

            # Injection scanning on the newest emails
            from src.security.injection_detector import scan_and_quarantine
            async with async_session() as session:
                result = await session.execute(
                    select(Email.id)
                    .where(Email.thread_id == thread_id)
                    .order_by(Email.date.desc())
                    .limit(new_email_count)
                )
                email_ids = list(result.scalars().all())

            for email_id in email_ids:
                await scan_and_quarantine(email_id)
        except Exception as e:
            logger.error(f"Post-processing failed for thread {thread_id}: {e}")

    async def _upsert_contact(
        self,
        session: AsyncSession,
        name: str | None,
        email: str | None,
        interaction_date: datetime | None,
    ) -> int:
        """Upsert a contact by email. Returns 1 if new, 0 if existing."""
        if not email:
            return 0
        stmt = pg_insert(Contact).values(
            email=email,
            name=name,
            last_interaction=interaction_date,
        ).on_conflict_do_update(
            index_elements=["email"],
            set_={
                "name": name if name else Contact.name,
                "last_interaction": interaction_date,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        result = await session.execute(stmt)
        return 1 if result.rowcount > 0 else 0


# Module-level singleton
sync_engine = SyncEngine()
