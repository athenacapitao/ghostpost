"""Tests for Gmail send/reply/draft operations."""

import base64
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from email import message_from_string

import pytest

from src.gmail.send import (
    FROM_EMAIL,
    FROM_NAME,
    _build_mime,
)


# ---------------------------------------------------------------------------
# Unit tests for _build_mime — no I/O, fully synchronous
# ---------------------------------------------------------------------------


class TestBuildMime:
    def test_basic_fields_are_set(self):
        raw = _build_mime(to="bob@example.com", subject="Hello", body="Hi there")
        msg = message_from_string(raw)
        assert msg["To"] == "bob@example.com"
        assert msg["Subject"] == "Hello"
        assert FROM_EMAIL in msg["From"]
        assert FROM_NAME in msg["From"]

    def test_to_list_is_joined(self):
        raw = _build_mime(
            to=["a@example.com", "b@example.com"],
            subject="Multi",
            body="Body",
        )
        msg = message_from_string(raw)
        assert "a@example.com" in msg["To"]
        assert "b@example.com" in msg["To"]

    def test_cc_header_included_when_provided(self):
        raw = _build_mime(
            to="a@example.com",
            subject="S",
            body="B",
            cc=["cc@example.com"],
        )
        msg = message_from_string(raw)
        assert msg["Cc"] == "cc@example.com"

    def test_cc_header_absent_when_not_provided(self):
        raw = _build_mime(to="a@example.com", subject="S", body="B")
        msg = message_from_string(raw)
        assert msg["Cc"] is None

    def test_in_reply_to_and_references_headers(self):
        raw = _build_mime(
            to="a@example.com",
            subject="Re: S",
            body="B",
            in_reply_to="<msg123@example.com>",
            references="<msg123@example.com>",
        )
        msg = message_from_string(raw)
        assert msg["In-Reply-To"] == "<msg123@example.com>"
        assert msg["References"] == "<msg123@example.com>"

    def test_threading_headers_absent_when_not_provided(self):
        raw = _build_mime(to="a@example.com", subject="S", body="B")
        msg = message_from_string(raw)
        assert msg["In-Reply-To"] is None
        assert msg["References"] is None

    def test_body_content(self):
        raw = _build_mime(to="a@example.com", subject="S", body="Hello world")
        msg = message_from_string(raw)
        payload = msg.get_payload(decode=True)
        assert b"Hello world" in payload


# ---------------------------------------------------------------------------
# Unit tests for GmailClient send/draft methods
# ---------------------------------------------------------------------------


class TestGmailClientSendMethods:
    """Test that GmailClient correctly delegates to the Gmail API."""

    def _make_client_with_mock_service(self):
        """Return a GmailClient with a fully mocked _service."""
        from src.gmail.client import GmailClient

        client = GmailClient.__new__(GmailClient)
        mock_service = MagicMock()
        # Cache the property so cached_property doesn't try to authenticate
        client.__dict__["_service"] = mock_service
        return client, mock_service

    @pytest.mark.asyncio
    async def test_send_message_encodes_raw_and_calls_api(self):
        client, mock_service = self._make_client_with_mock_service()
        sent_body = {}

        def capture_send(**kwargs):
            sent_body.update(kwargs)
            mock_execute = MagicMock(return_value={"id": "msg1"})
            m = MagicMock()
            m.execute = mock_execute
            return m

        mock_service.users().messages().send.side_effect = capture_send

        result = await client.send_message("raw email content")

        assert result == {"id": "msg1"}
        assert sent_body["userId"] == "me"
        # Verify the raw field is base64url-encoded
        decoded = base64.urlsafe_b64decode(sent_body["body"]["raw"]).decode()
        assert decoded == "raw email content"

    @pytest.mark.asyncio
    async def test_create_gmail_draft_without_thread_id(self):
        client, mock_service = self._make_client_with_mock_service()
        created_body = {}

        def capture_create(**kwargs):
            created_body.update(kwargs)
            mock_execute = MagicMock(return_value={"id": "draft1"})
            m = MagicMock()
            m.execute = mock_execute
            return m

        mock_service.users().drafts().create.side_effect = capture_create

        result = await client.create_gmail_draft("raw content")

        assert result == {"id": "draft1"}
        assert created_body["userId"] == "me"
        assert "threadId" not in created_body["body"]["message"]

    @pytest.mark.asyncio
    async def test_create_gmail_draft_with_thread_id(self):
        client, mock_service = self._make_client_with_mock_service()
        created_body = {}

        def capture_create(**kwargs):
            created_body.update(kwargs)
            mock_execute = MagicMock(return_value={"id": "draft2"})
            m = MagicMock()
            m.execute = mock_execute
            return m

        mock_service.users().drafts().create.side_effect = capture_create

        result = await client.create_gmail_draft("raw content", thread_id="thread123")

        assert result == {"id": "draft2"}
        assert created_body["body"]["message"]["threadId"] == "thread123"

    @pytest.mark.asyncio
    async def test_send_gmail_draft(self):
        client, mock_service = self._make_client_with_mock_service()
        sent_body = {}

        def capture_send(**kwargs):
            sent_body.update(kwargs)
            mock_execute = MagicMock(return_value={"id": "msg2"})
            m = MagicMock()
            m.execute = mock_execute
            return m

        mock_service.users().drafts().send.side_effect = capture_send

        result = await client.send_gmail_draft("draft1")

        assert result == {"id": "msg2"}
        assert sent_body["body"] == {"id": "draft1"}

    @pytest.mark.asyncio
    async def test_delete_gmail_draft(self):
        client, mock_service = self._make_client_with_mock_service()
        deleted_args = {}

        def capture_delete(**kwargs):
            deleted_args.update(kwargs)
            mock_execute = MagicMock(return_value=None)
            m = MagicMock()
            m.execute = mock_execute
            return m

        mock_service.users().drafts().delete.side_effect = capture_delete

        await client.delete_gmail_draft("draft99")

        assert deleted_args["id"] == "draft99"
        assert deleted_args["userId"] == "me"


# ---------------------------------------------------------------------------
# Integration-style tests for high-level send functions (mocked DB + API)
# ---------------------------------------------------------------------------


class TestSendFunctions:
    """Test send_reply, send_new, create_draft, approve_draft, reject_draft
    with mocked database sessions and GmailClient calls."""

    @pytest.mark.asyncio
    async def test_send_new_calls_client_and_logs(self):
        mock_result = {"id": "gmail_msg_1"}

        with (
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", new_callable=AsyncMock) as mock_log,
        ):
            mock_client.send_message = AsyncMock(return_value=mock_result)

            from src.gmail.send import send_new

            result = await send_new(
                to="recipient@example.com",
                subject="Test subject",
                body="Test body",
                actor="test_actor",
            )

        assert result == mock_result
        mock_client.send_message.assert_awaited_once()
        mock_log.assert_awaited_once_with(
            action_type="email_sent",
            actor="test_actor",
            details={
                "to": "recipient@example.com",
                "subject": "Test subject",
                "gmail_id": "gmail_msg_1",
            },
        )

    @pytest.mark.asyncio
    async def test_send_reply_prepends_re_prefix(self):
        """send_reply should prepend 'Re: ' to subjects that don't already have it."""
        mock_email = MagicMock()
        mock_email.message_id = "<orig@example.com>"
        mock_email.subject = "Original subject"
        mock_email.from_address = "sender@example.com"

        mock_thread = MagicMock()
        mock_thread.gmail_thread_id = "gthread1"

        mock_result = {"id": "reply_msg"}

        with (
            patch("src.gmail.send.async_session") as mock_session_factory,
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
        ):
            # Set up the async context manager for the session
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            # First call: select Email; second call: session.get Thread
            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.return_value = mock_email
            mock_session.execute = AsyncMock(return_value=mock_execute_result)
            mock_session.get = AsyncMock(return_value=mock_thread)

            mock_client.send_message = AsyncMock(return_value=mock_result)

            from src.gmail.send import send_reply

            result = await send_reply(thread_id=1, body="My reply", actor="user")

        assert result == mock_result
        # Verify Re: prefix was added
        call_args = mock_client.send_message.call_args[0][0]
        msg = message_from_string(call_args)
        assert msg["Subject"].startswith("Re:")

    @pytest.mark.asyncio
    async def test_send_reply_raises_when_no_emails_in_thread(self):
        with patch("src.gmail.send.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_execute_result = MagicMock()
            mock_execute_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_execute_result)

            from src.gmail.send import send_reply

            with pytest.raises(ValueError, match="No emails found"):
                await send_reply(thread_id=999, body="reply")

    @pytest.mark.asyncio
    async def test_approve_draft_raises_when_not_found(self):
        with patch("src.gmail.send.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = AsyncMock(return_value=None)

            from src.gmail.send import approve_draft

            with pytest.raises(ValueError, match="not found"):
                await approve_draft(draft_id=999)

    @pytest.mark.asyncio
    async def test_approve_draft_raises_when_not_pending(self):
        mock_draft = MagicMock()
        mock_draft.status = "sent"

        with patch("src.gmail.send.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = AsyncMock(return_value=mock_draft)

            from src.gmail.send import approve_draft

            with pytest.raises(ValueError, match="not pending"):
                await approve_draft(draft_id=1)

    @pytest.mark.asyncio
    async def test_reject_draft_raises_when_not_found(self):
        with patch("src.gmail.send.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = AsyncMock(return_value=None)

            from src.gmail.send import reject_draft

            with pytest.raises(ValueError, match="not found"):
                await reject_draft(draft_id=999)

    @pytest.mark.asyncio
    async def test_reject_draft_raises_when_not_pending(self):
        mock_draft = MagicMock()
        mock_draft.status = "rejected"

        with patch("src.gmail.send.async_session") as mock_session_factory:
            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_session.get = AsyncMock(return_value=mock_draft)

            from src.gmail.send import reject_draft

            with pytest.raises(ValueError, match="not pending"):
                await reject_draft(draft_id=1)


# ---------------------------------------------------------------------------
# Tests for create_thread_from_compose
# ---------------------------------------------------------------------------


def _make_pg_insert_mock():
    """Build a chainable mock for pg_insert(...).values(...).on_conflict_do_update(...)."""
    stmt_mock = MagicMock()
    stmt_mock.values.return_value = stmt_mock
    stmt_mock.on_conflict_do_update.return_value = stmt_mock
    stmt_mock.on_conflict_do_nothing.return_value = stmt_mock
    return stmt_mock


class TestCreateThreadFromCompose:
    """Unit tests for create_thread_from_compose — all DB and Gmail I/O mocked."""

    def _make_session_mock(self, thread_id: int = 42):
        """Return a mock async_session context manager that yields the inner session."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # begin() must itself be an async context manager.
        # AsyncMock sets up __aenter__/__aexit__ automatically when used as a
        # context manager in async with — we just need to make begin() return
        # an AsyncMock instance (not a coroutine).
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=None)
        mock_begin.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock(return_value=mock_begin)

        # execute() returns an object whose scalar_one() gives thread_id
        mock_execute_result = MagicMock()
        mock_execute_result.scalar_one.return_value = thread_id
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        return mock_session

    @pytest.mark.asyncio
    async def test_returns_thread_id_when_thread_id_present_in_result(self):
        """When gmail_result includes threadId, no extra API call is made."""
        gmail_result = {"id": "msg1", "threadId": "gthread1"}
        mock_session = self._make_session_mock(thread_id=7)

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", return_value=_make_pg_insert_mock()),
        ):
            from src.gmail.send import create_thread_from_compose

            result = await create_thread_from_compose(
                gmail_result=gmail_result,
                to="bob@example.com",
                subject="Hello Bob",
                body="Body text",
            )

        assert result == 7

    @pytest.mark.asyncio
    async def test_fetches_thread_id_from_gmail_when_missing(self):
        """When gmail_result has no threadId, get_message is called to fetch it."""
        gmail_result = {"id": "msg2"}  # no threadId
        mock_session = self._make_session_mock(thread_id=12)

        mock_get_message = AsyncMock(return_value={"threadId": "gthread_fetched"})

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", return_value=_make_pg_insert_mock()),
            patch("src.gmail.send._client") as mock_client,
        ):
            mock_client.get_message = mock_get_message
            from src.gmail.send import create_thread_from_compose

            result = await create_thread_from_compose(
                gmail_result=gmail_result,
                to="bob@example.com",
                subject="Hello",
                body="Body",
            )

        mock_get_message.assert_awaited_once_with("msg2")
        assert result == 12

    @pytest.mark.asyncio
    async def test_goal_sets_goal_status_in_progress(self):
        """Providing a goal should set goal_status to 'in_progress'."""
        gmail_result = {"id": "msg3", "threadId": "gthread3"}
        mock_session = self._make_session_mock(thread_id=5)
        captured_values: list[dict] = []

        def capturing_pg_insert(model):
            stmt = _make_pg_insert_mock()
            def capture_values(**kwargs):
                captured_values.append(kwargs)
                return stmt
            stmt.values.side_effect = lambda **kw: (captured_values.append(kw), stmt)[1]
            return stmt

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", side_effect=capturing_pg_insert),
        ):
            from src.gmail.send import create_thread_from_compose

            await create_thread_from_compose(
                gmail_result=gmail_result,
                to="alice@example.com",
                subject="Goal test",
                body="Body",
                goal="Close the deal",
                acceptance_criteria="Signed contract received",
            )

        # The first captured call should be the thread upsert
        assert len(captured_values) >= 1
        thread_values = captured_values[0]
        assert thread_values.get("goal") == "Close the deal"
        assert thread_values.get("goal_status") == "in_progress"
        assert thread_values.get("acceptance_criteria") == "Signed contract received"

    @pytest.mark.asyncio
    async def test_default_follow_up_days_is_three(self):
        """When follow_up_days is None, next_follow_up_date should be ~3 days out."""
        from datetime import timezone
        gmail_result = {"id": "msg4", "threadId": "gthread4"}
        mock_session = self._make_session_mock(thread_id=8)
        captured_values: list[dict] = []

        def capturing_pg_insert(model):
            stmt = _make_pg_insert_mock()
            stmt.values.side_effect = lambda **kw: (captured_values.append(kw), stmt)[1]
            return stmt

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", side_effect=capturing_pg_insert),
        ):
            from datetime import datetime, timedelta
            before = datetime.now(timezone.utc)

            from src.gmail.send import create_thread_from_compose
            await create_thread_from_compose(
                gmail_result=gmail_result,
                to="test@example.com",
                subject="Follow-up test",
                body="Body",
            )

            after = datetime.now(timezone.utc)

        thread_values = captured_values[0]
        fup_date = thread_values.get("next_follow_up_date")
        assert fup_date is not None
        expected_low = before + timedelta(days=3)
        expected_high = after + timedelta(days=3)
        assert expected_low <= fup_date <= expected_high

    @pytest.mark.asyncio
    async def test_custom_follow_up_days_respected(self):
        """follow_up_days=7 should produce next_follow_up_date ~7 days out."""
        from datetime import timezone
        gmail_result = {"id": "msg5", "threadId": "gthread5"}
        mock_session = self._make_session_mock(thread_id=9)
        captured_values: list[dict] = []

        def capturing_pg_insert(model):
            stmt = _make_pg_insert_mock()
            stmt.values.side_effect = lambda **kw: (captured_values.append(kw), stmt)[1]
            return stmt

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", side_effect=capturing_pg_insert),
        ):
            from datetime import datetime, timedelta
            before = datetime.now(timezone.utc)

            from src.gmail.send import create_thread_from_compose
            await create_thread_from_compose(
                gmail_result=gmail_result,
                to="test@example.com",
                subject="Custom follow-up",
                body="Body",
                follow_up_days=7,
            )

            after = datetime.now(timezone.utc)

        thread_values = captured_values[0]
        fup_date = thread_values.get("next_follow_up_date")
        expected_low = before + timedelta(days=7)
        expected_high = after + timedelta(days=7)
        assert expected_low <= fup_date <= expected_high

    @pytest.mark.asyncio
    async def test_state_is_always_waiting_reply(self):
        """New threads from compose should start in WAITING_REPLY state."""
        gmail_result = {"id": "msg6", "threadId": "gthread6"}
        mock_session = self._make_session_mock(thread_id=10)
        captured_values: list[dict] = []

        def capturing_pg_insert(model):
            stmt = _make_pg_insert_mock()
            stmt.values.side_effect = lambda **kw: (captured_values.append(kw), stmt)[1]
            return stmt

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", side_effect=capturing_pg_insert),
        ):
            from src.gmail.send import create_thread_from_compose
            await create_thread_from_compose(
                gmail_result=gmail_result,
                to="test@example.com",
                subject="State test",
                body="Body",
            )

        thread_values = captured_values[0]
        assert thread_values.get("state") == "WAITING_REPLY"

    @pytest.mark.asyncio
    async def test_to_string_converted_to_list_for_email_record(self):
        """A string 'to' value should be stored as a list in the email record."""
        gmail_result = {"id": "msg7", "threadId": "gthread7"}
        mock_session = self._make_session_mock(thread_id=11)
        captured_values: list[dict] = []

        def capturing_pg_insert(model):
            stmt = _make_pg_insert_mock()
            stmt.values.side_effect = lambda **kw: (captured_values.append(kw), stmt)[1]
            return stmt

        with (
            patch("src.gmail.send.async_session", return_value=mock_session),
            patch("src.gmail.send.pg_insert", side_effect=capturing_pg_insert),
        ):
            from src.gmail.send import create_thread_from_compose
            await create_thread_from_compose(
                gmail_result=gmail_result,
                to="single@example.com",
                subject="To list test",
                body="Body",
            )

        # Second captured call is the email upsert
        assert len(captured_values) >= 2
        email_values = captured_values[1]
        assert email_values.get("to_addresses") == ["single@example.com"]


# ---------------------------------------------------------------------------
# Tests for ComposeRequest schema validation
# ---------------------------------------------------------------------------


class TestComposeRequestSchema:
    def test_valid_auto_reply_mode_accepted(self):
        from src.api.schemas import ComposeRequest
        for mode in ("off", "draft", "auto"):
            req = ComposeRequest(to="a@b.com", subject="S", body="B", auto_reply_mode=mode)
            assert req.auto_reply_mode == mode

    def test_invalid_auto_reply_mode_rejected(self):
        from pydantic import ValidationError
        from src.api.schemas import ComposeRequest
        with pytest.raises(ValidationError, match="auto_reply_mode"):
            ComposeRequest(to="a@b.com", subject="S", body="B", auto_reply_mode="instant")

    def test_valid_priority_accepted(self):
        from src.api.schemas import ComposeRequest
        for p in ("low", "medium", "high", "critical"):
            req = ComposeRequest(to="a@b.com", subject="S", body="B", priority=p)
            assert req.priority == p

    def test_invalid_priority_rejected(self):
        from pydantic import ValidationError
        from src.api.schemas import ComposeRequest
        with pytest.raises(ValidationError, match="priority"):
            ComposeRequest(to="a@b.com", subject="S", body="B", priority="urgent")

    def test_all_optional_fields_default_to_none(self):
        from src.api.schemas import ComposeRequest
        req = ComposeRequest(to="a@b.com", subject="S", body="B")
        assert req.goal is None
        assert req.acceptance_criteria is None
        assert req.playbook is None
        assert req.auto_reply_mode is None
        assert req.follow_up_days is None
        assert req.priority is None
        assert req.category is None
        assert req.notes is None

    def test_all_agent_context_fields_accepted(self):
        from src.api.schemas import ComposeRequest
        req = ComposeRequest(
            to="a@b.com",
            subject="S",
            body="B",
            goal="Close deal",
            acceptance_criteria="Contract signed",
            playbook="sales",
            auto_reply_mode="draft",
            follow_up_days=5,
            priority="high",
            category="sales",
            notes="This is a hot lead",
        )
        assert req.goal == "Close deal"
        assert req.follow_up_days == 5
        assert req.priority == "high"
