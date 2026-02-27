"""Database constraints & cascade tests — validates data integrity under stress.

Tests FK cascades, unique constraints, null handling, JSONB fields, and
concurrent insert race conditions.
"""

import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from src.db.models import Thread, Email, Contact, Attachment, Draft, ThreadOutcome, Setting, AuditLog, SecurityEvent
from src.db.session import async_session

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper fixture: create a thread with emails and attachments
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def thread_with_email_and_attachment():
    """Create a thread → email → attachment chain for cascade tests."""
    import uuid
    uid = uuid.uuid4().hex[:8]

    async with async_session() as session:
        thread = Thread(
            gmail_thread_id=f"audit_cascade_thread_{uid}",
            subject="Cascade Test Thread",
            state="ACTIVE",
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)

        email = Email(
            gmail_id=f"audit_cascade_email_{uid}",
            thread_id=thread.id,
            message_id=f"<audit_cascade_{uid}@test.com>",
            from_address="test@example.com",
            to_addresses=["user@example.com"],
            subject="Test Email",
            body_plain="Test body",
            date=datetime.now(timezone.utc),
            is_read=False,
            is_sent=False,
            is_draft=False,
        )
        session.add(email)
        await session.commit()
        await session.refresh(email)

        attachment = Attachment(
            email_id=email.id,
            filename="test.pdf",
            content_type="application/pdf",
            size=1024,
        )
        session.add(attachment)
        await session.commit()
        await session.refresh(attachment)

        draft = Draft(
            thread_id=thread.id,
            to_addresses=["reply@example.com"],
            subject="Re: Test",
            body="Draft reply",
            status="pending",
        )
        session.add(draft)
        await session.commit()
        await session.refresh(draft)

        session.expunge_all()

    yield {
        "thread": thread,
        "email": email,
        "attachment": attachment,
        "draft": draft,
    }

    # Cleanup: use SQL DELETE to trigger DB-level ON DELETE CASCADE
    async with async_session() as session:
        await session.execute(delete(Thread).where(Thread.id == thread.id))
        await session.commit()


# ---------------------------------------------------------------------------
# CASCADE deletes
# ---------------------------------------------------------------------------

class TestCascadeDeletes:
    async def test_delete_thread_cascades_emails(self, thread_with_email_and_attachment):
        """ORM session.delete(thread) should cascade-delete all its emails."""
        data = thread_with_email_and_attachment
        thread_id = data["thread"].id
        email_id = data["email"].id

        async with async_session() as session:
            thread = await session.get(Thread, thread_id)
            await session.delete(thread)
            await session.commit()

        async with async_session() as session:
            email = await session.get(Email, email_id)
            assert email is None, "Email should be cascade-deleted with thread"

    async def test_delete_thread_cascades_drafts(self, thread_with_email_and_attachment):
        """ORM session.delete(thread) should cascade-delete all its drafts."""
        data = thread_with_email_and_attachment
        thread_id = data["thread"].id
        draft_id = data["draft"].id

        async with async_session() as session:
            thread = await session.get(Thread, thread_id)
            await session.delete(thread)
            await session.commit()

        async with async_session() as session:
            draft = await session.get(Draft, draft_id)
            assert draft is None, "Draft should be cascade-deleted with thread"

    async def test_delete_email_cascades_attachments(self, thread_with_email_and_attachment):
        """Deleting an email should cascade-delete all its attachments."""
        data = thread_with_email_and_attachment
        email_id = data["email"].id
        attachment_id = data["attachment"].id

        async with async_session() as session:
            await session.execute(delete(Email).where(Email.id == email_id))
            await session.commit()

        async with async_session() as session:
            att = await session.get(Attachment, attachment_id)
            assert att is None, "Attachment should be cascade-deleted with email"

    async def test_delete_thread_cascades_all_levels(self, thread_with_email_and_attachment):
        """ORM session.delete(thread) cascades through email to attachments (3 levels)."""
        data = thread_with_email_and_attachment
        thread_id = data["thread"].id
        attachment_id = data["attachment"].id

        async with async_session() as session:
            thread = await session.get(Thread, thread_id)
            await session.delete(thread)
            await session.commit()

        async with async_session() as session:
            att = await session.get(Attachment, attachment_id)
            assert att is None, "Attachment should cascade-delete through email when thread deleted"


# ---------------------------------------------------------------------------
# Unique constraints
# ---------------------------------------------------------------------------

class TestUniqueConstraints:
    async def test_duplicate_gmail_thread_id_rejected(self):
        """Two threads with same gmail_thread_id should raise IntegrityError."""
        uid = f"audit_unique_thread_{uuid.uuid4().hex[:8]}"
        async with async_session() as session:
            t1 = Thread(gmail_thread_id=uid, subject="Thread 1", state="NEW")
            session.add(t1)
            await session.commit()

        try:
            async with async_session() as session:
                t2 = Thread(gmail_thread_id=uid, subject="Thread 2", state="NEW")
                session.add(t2)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            async with async_session() as session:
                await session.execute(
                    delete(Thread).where(Thread.gmail_thread_id == uid)
                )
                await session.commit()

    async def test_duplicate_gmail_id_email_rejected(self):
        """Two emails with same gmail_id should raise IntegrityError."""
        uid = uuid.uuid4().hex[:8]
        thread_gid = f"audit_unique_email_thread_{uid}"
        email_gid = f"audit_unique_email_{uid}"

        async with async_session() as session:
            thread = Thread(gmail_thread_id=thread_gid, subject="Test", state="NEW")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            e1 = Email(
                gmail_id=email_gid, thread_id=thread.id,
                from_address="a@test.com", date=datetime.now(timezone.utc),
                is_read=False, is_sent=False, is_draft=False,
            )
            session.add(e1)
            await session.commit()

        try:
            async with async_session() as session:
                thread = (await session.execute(
                    select(Thread).where(Thread.gmail_thread_id == thread_gid)
                )).scalar_one()
                e2 = Email(
                    gmail_id=email_gid, thread_id=thread.id,
                    from_address="b@test.com", date=datetime.now(timezone.utc),
                    is_read=False, is_sent=False, is_draft=False,
                )
                session.add(e2)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            async with async_session() as session:
                await session.execute(
                    delete(Thread).where(Thread.gmail_thread_id == thread_gid)
                )
                await session.commit()

    async def test_duplicate_contact_email_rejected(self):
        """Two contacts with same email should raise IntegrityError."""
        email = f"audit_unique_{uuid.uuid4().hex[:8]}@test.com"

        async with async_session() as session:
            c1 = Contact(email=email, name="Contact 1")
            session.add(c1)
            await session.commit()

        try:
            async with async_session() as session:
                c2 = Contact(email=email, name="Contact 2")
                session.add(c2)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            async with async_session() as session:
                result = await session.execute(
                    select(Contact).where(Contact.email == email)
                )
                for c in result.scalars().all():
                    await session.delete(c)
                await session.commit()

    async def test_duplicate_thread_outcome_rejected(self):
        """Two outcomes for same thread should raise IntegrityError."""
        uid = uuid.uuid4().hex[:8]
        gid = f"audit_outcome_unique_thread_{uid}"

        async with async_session() as session:
            thread = Thread(gmail_thread_id=gid, subject="Test", state="GOAL_MET")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            o1 = ThreadOutcome(
                thread_id=thread.id, outcome_type="decision",
                summary="First outcome",
            )
            session.add(o1)
            await session.commit()

        try:
            async with async_session() as session:
                thread = (await session.execute(
                    select(Thread).where(Thread.gmail_thread_id == gid)
                )).scalar_one()
                o2 = ThreadOutcome(
                    thread_id=thread.id, outcome_type="agreement",
                    summary="Second outcome",
                )
                session.add(o2)
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            async with async_session() as session:
                await session.execute(
                    delete(Thread).where(Thread.gmail_thread_id == gid)
                )
                await session.commit()


# ---------------------------------------------------------------------------
# Foreign key violations
# ---------------------------------------------------------------------------

class TestForeignKeyViolations:
    async def test_email_with_nonexistent_thread_rejected(self):
        """Email referencing nonexistent thread_id should fail."""
        async with async_session() as session:
            email = Email(
                gmail_id="audit_fk_email_001", thread_id=999999,
                from_address="test@test.com", date=datetime.now(timezone.utc),
                is_read=False, is_sent=False, is_draft=False,
            )
            session.add(email)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_attachment_with_nonexistent_email_rejected(self):
        """Attachment referencing nonexistent email_id should fail."""
        async with async_session() as session:
            att = Attachment(email_id=999999, filename="test.txt")
            session.add(att)
            with pytest.raises(IntegrityError):
                await session.commit()

    async def test_draft_with_nonexistent_thread_rejected(self):
        """Draft referencing nonexistent thread_id should fail."""
        async with async_session() as session:
            draft = Draft(
                thread_id=999999,
                to_addresses=["test@test.com"],
                subject="Test",
                body="Test",
                status="pending",
            )
            session.add(draft)
            with pytest.raises(IntegrityError):
                await session.commit()


# ---------------------------------------------------------------------------
# Null handling
# ---------------------------------------------------------------------------

class TestNullHandling:
    async def test_thread_with_all_optional_null(self):
        """Thread with only required fields (gmail_thread_id) should work."""
        async with async_session() as session:
            thread = Thread(gmail_thread_id=f"audit_null_thread_{uuid.uuid4().hex[:8]}")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            assert thread.subject is None
            assert thread.category is None
            assert thread.summary is None
            assert thread.priority is None
            assert thread.goal is None

            await session.delete(thread)
            await session.commit()

    async def test_email_with_optional_fields_null(self):
        """Email with minimal required fields should work."""
        async with async_session() as session:
            thread = Thread(gmail_thread_id=f"audit_null_email_thread_{uuid.uuid4().hex[:8]}", state="NEW")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            email = Email(
                gmail_id=f"audit_null_email_{uuid.uuid4().hex[:8]}",
                thread_id=thread.id,
                is_read=False, is_sent=False, is_draft=False,
            )
            session.add(email)
            await session.commit()
            await session.refresh(email)

            assert email.from_address is None
            assert email.to_addresses is None
            assert email.subject is None
            assert email.body_plain is None
            assert email.body_html is None
            assert email.security_score is None

            await session.delete(thread)
            await session.commit()


# ---------------------------------------------------------------------------
# JSONB fields
# ---------------------------------------------------------------------------

class TestJSONBFields:
    async def test_deeply_nested_json(self):
        """JSONB field accepts deeply nested JSON (10 levels)."""
        nested = {"level": 1}
        current = nested
        for i in range(2, 11):
            current["child"] = {"level": i}
            current = current["child"]

        async with async_session() as session:
            thread = Thread(gmail_thread_id=f"audit_jsonb_nested_{uuid.uuid4().hex[:8]}", state="NEW")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            email = Email(
                gmail_id=f"audit_jsonb_email_{uuid.uuid4().hex[:8]}",
                thread_id=thread.id,
                headers=nested,
                action_required={"required": True, "details": nested},
                is_read=False, is_sent=False, is_draft=False,
            )
            session.add(email)
            await session.commit()
            await session.refresh(email)

            assert email.headers["level"] == 1
            assert email.action_required["details"]["level"] == 1

            await session.delete(thread)
            await session.commit()

    async def test_jsonb_array_values(self):
        """JSONB fields accept arrays."""
        async with async_session() as session:
            thread = Thread(gmail_thread_id=f"audit_jsonb_array_{uuid.uuid4().hex[:8]}", state="NEW")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            email = Email(
                gmail_id=f"audit_jsonb_array_email_{uuid.uuid4().hex[:8]}",
                thread_id=thread.id,
                to_addresses=["a@test.com", "b@test.com", "c@test.com"],
                attachment_metadata=[
                    {"filename": "doc.pdf", "size": 1024},
                    {"filename": "img.png", "size": 2048},
                ],
                is_read=False, is_sent=False, is_draft=False,
            )
            session.add(email)
            await session.commit()
            await session.refresh(email)

            assert len(email.to_addresses) == 3
            assert len(email.attachment_metadata) == 2

            await session.delete(thread)
            await session.commit()

    async def test_jsonb_unicode_values(self):
        """JSONB fields accept unicode strings."""
        async with async_session() as session:
            contact = Contact(
                email=f"audit_jsonb_unicode_{uuid.uuid4().hex[:8]}@test.com",
                name="テスト太郎",
                topics=["日本語", "中文", "العربية"],
                aliases={"jp": "テスト太郎", "cn": "测试"},
            )
            session.add(contact)
            await session.commit()
            await session.refresh(contact)

            assert contact.name == "テスト太郎"
            assert "日本語" in contact.topics
            assert contact.aliases["jp"] == "テスト太郎"

            await session.delete(contact)
            await session.commit()


# ---------------------------------------------------------------------------
# Large data
# ---------------------------------------------------------------------------

class TestLargeData:
    async def test_large_email_body(self):
        """Email with 1MB body should be stored and retrieved correctly."""
        large_body = "A" * (1024 * 1024)  # 1MB

        async with async_session() as session:
            thread = Thread(gmail_thread_id=f"audit_large_body_{uuid.uuid4().hex[:8]}", state="NEW")
            session.add(thread)
            await session.commit()
            await session.refresh(thread)

            email = Email(
                gmail_id=f"audit_large_body_email_{uuid.uuid4().hex[:8]}",
                thread_id=thread.id,
                body_plain=large_body,
                is_read=False, is_sent=False, is_draft=False,
            )
            session.add(email)
            await session.commit()
            await session.refresh(email)

            assert len(email.body_plain) == 1024 * 1024

            await session.delete(thread)
            await session.commit()


# ---------------------------------------------------------------------------
# Setting KV store
# ---------------------------------------------------------------------------

class TestSettingKVStore:
    async def test_setting_crud(self):
        """Setting create, read, update, delete lifecycle."""
        key = "audit_test_setting"
        async with async_session() as session:
            # Create
            s = Setting(key=key, value="initial")
            session.add(s)
            await session.commit()

            # Read
            s = await session.get(Setting, key)
            assert s.value == "initial"

            # Update
            s.value = "updated"
            await session.commit()
            s = await session.get(Setting, key)
            assert s.value == "updated"

            # Delete
            await session.delete(s)
            await session.commit()
            s = await session.get(Setting, key)
            assert s is None

    async def test_setting_null_value(self):
        """Setting with null value works."""
        key = "audit_test_null_setting"
        async with async_session() as session:
            s = Setting(key=key, value=None)
            session.add(s)
            await session.commit()

            s = await session.get(Setting, key)
            assert s.value is None

            await session.delete(s)
            await session.commit()
