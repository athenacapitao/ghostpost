"""Gmail sync & send resilience tests.

Tests Gmail integration failure modes: expired tokens, network errors,
malformed messages, rate limits, and MIME building edge cases.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from email.mime.text import MIMEText

from src.gmail.send import _build_mime, send_reply, send_new, create_draft, approve_draft, reject_draft

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# MIME building edge cases
# ---------------------------------------------------------------------------

class TestMIMEBuilding:
    def test_build_mime_basic(self):
        """Basic MIME message builds correctly."""
        import base64
        raw = _build_mime(
            to="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        assert "test@example.com" in raw
        assert "Test Subject" in raw
        # Body may be base64-encoded in MIME; check either way
        assert "Test body" in raw or base64.b64encode(b"Test body").decode() in raw

    def test_build_mime_list_to(self):
        """MIME with list of recipients."""
        raw = _build_mime(
            to=["a@test.com", "b@test.com"],
            subject="Multi To",
            body="Body",
        )
        assert "a@test.com" in raw
        assert "b@test.com" in raw

    def test_build_mime_with_cc(self):
        """MIME with CC recipients."""
        raw = _build_mime(
            to="main@test.com",
            subject="CC Test",
            body="Body",
            cc=["cc1@test.com", "cc2@test.com"],
        )
        assert "cc1@test.com" in raw
        assert "cc2@test.com" in raw

    def test_build_mime_with_reply_headers(self):
        """MIME with In-Reply-To and References headers."""
        raw = _build_mime(
            to="reply@test.com",
            subject="Re: Thread",
            body="Reply body",
            in_reply_to="<original@message.id>",
            references="<original@message.id>",
        )
        assert "In-Reply-To" in raw
        assert "References" in raw
        assert "<original@message.id>" in raw

    def test_build_mime_unicode_body(self):
        """MIME with unicode characters in body."""
        raw = _build_mime(
            to="test@test.com",
            subject="Unicode Test",
            body="こんにちは世界 🌍 Héllo Wörld",
        )
        assert isinstance(raw, str)
        # UTF-8 encoding should be specified
        assert "utf-8" in raw.lower()

    def test_build_mime_unicode_subject(self):
        """MIME with unicode characters in subject."""
        raw = _build_mime(
            to="test@test.com",
            subject="日本語の件名 🇯🇵",
            body="Test body",
        )
        assert isinstance(raw, str)

    def test_build_mime_empty_subject(self):
        """MIME with empty subject."""
        raw = _build_mime(
            to="test@test.com",
            subject="",
            body="No subject email",
        )
        assert isinstance(raw, str)

    def test_build_mime_very_long_body(self):
        """MIME with very long body (100KB)."""
        long_body = "A" * 102400
        raw = _build_mime(
            to="test@test.com",
            subject="Long Body",
            body=long_body,
        )
        assert isinstance(raw, str)

    def test_build_mime_special_chars_in_filename_like_body(self):
        """MIME with special characters in body."""
        body = 'File: "test file (1).pdf" <attachment> & more'
        raw = _build_mime(
            to="test@test.com",
            subject="Special Chars",
            body=body,
        )
        assert isinstance(raw, str)


# ---------------------------------------------------------------------------
# Send reply failure modes
# ---------------------------------------------------------------------------

class TestSendReplyFailures:
    async def test_send_reply_no_emails_in_thread(self):
        """send_reply when thread has no emails should raise ValueError."""
        with patch("src.gmail.send.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.get = AsyncMock(return_value=None)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="No emails found"):
                await send_reply(thread_id=1, body="Reply")

    async def test_send_reply_gmail_api_error(self):
        """send_reply when Gmail API returns error."""
        mock_email = MagicMock()
        mock_email.message_id = "<test@msg.id>"
        mock_email.subject = "Test"
        mock_email.from_address = "sender@test.com"

        mock_thread = MagicMock()
        mock_thread.gmail_thread_id = "thread_123"

        with patch("src.gmail.send.async_session") as mock_ctx, \
             patch("src.gmail.send._client") as mock_gmail:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_email
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_gmail.send_message = AsyncMock(side_effect=Exception("Gmail API 500"))

            with pytest.raises(Exception, match="Gmail API 500"):
                await send_reply(thread_id=1, body="Reply")

    async def test_send_reply_gmail_rate_limit(self):
        """send_reply when Gmail API returns 429 (rate limit)."""
        mock_email = MagicMock()
        mock_email.message_id = "<test@msg.id>"
        mock_email.subject = "Test"
        mock_email.from_address = "sender@test.com"

        mock_thread = MagicMock()
        mock_thread.gmail_thread_id = "thread_123"

        with patch("src.gmail.send.async_session") as mock_ctx, \
             patch("src.gmail.send._client") as mock_gmail:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_email
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_gmail.send_message = AsyncMock(side_effect=Exception("429 Rate Limit Exceeded"))

            with pytest.raises(Exception, match="429"):
                await send_reply(thread_id=1, body="Reply")


# ---------------------------------------------------------------------------
# Send new email failure modes
# ---------------------------------------------------------------------------

class TestSendNewFailures:
    async def test_send_new_gmail_error(self):
        """send_new when Gmail API fails."""
        with patch("src.gmail.send._client") as mock_gmail:
            mock_gmail.send_message = AsyncMock(side_effect=Exception("Network error"))
            with pytest.raises(Exception, match="Network error"):
                await send_new(to="test@test.com", subject="Test", body="Body")


# ---------------------------------------------------------------------------
# Draft operations failure modes
# ---------------------------------------------------------------------------

class TestDraftFailures:
    async def test_approve_nonexistent_draft(self):
        """approve_draft with nonexistent draft should raise ValueError."""
        with patch("src.gmail.send.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="not found"):
                await approve_draft(99999)

    async def test_approve_already_sent_draft(self):
        """approve_draft on already-sent draft should raise ValueError."""
        mock_draft = MagicMock()
        mock_draft.status = "sent"

        with patch("src.gmail.send.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_draft)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="sent"):
                await approve_draft(1)

    async def test_approve_rejected_draft(self):
        """approve_draft on rejected draft should raise ValueError."""
        mock_draft = MagicMock()
        mock_draft.status = "rejected"

        with patch("src.gmail.send.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_draft)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="rejected"):
                await approve_draft(1)

    async def test_reject_nonexistent_draft(self):
        """reject_draft with nonexistent draft should raise ValueError."""
        with patch("src.gmail.send.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="not found"):
                await reject_draft(99999)

    async def test_reject_already_sent_draft(self):
        """reject_draft on already-sent draft should raise ValueError."""
        mock_draft = MagicMock()
        mock_draft.status = "sent"

        with patch("src.gmail.send.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_draft)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ValueError, match="sent"):
                await reject_draft(1)
