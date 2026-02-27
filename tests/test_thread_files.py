"""Tests for thread-to-markdown export functions in src/engine/context_writer.py.

Tests cover:
- _format_size: byte formatting
- _format_addresses: JSONB address normalisation
- _build_thread_markdown: markdown rendering logic (pure, no DB)
- write_single_thread_file: DB + filesystem integration (mocked)
- write_thread_files: bulk export + orphan cleanup (mocked)
- write_email_context: new per-thread file reference line
"""

import json
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_email(
    email_id: int = 1,
    from_address: str = "sender@example.com",
    to_addresses: list | dict | None = None,
    body_plain: str | None = "Hello there",
    body_html: str | None = None,
    date: datetime | None = None,
    is_sent: bool = False,
    sentiment: str | None = None,
    urgency: str | None = None,
    action_required: dict | None = None,
    security_score: int | None = None,
    attachments: list | None = None,
) -> MagicMock:
    email = MagicMock()
    email.id = email_id
    email.from_address = from_address
    email.to_addresses = to_addresses if to_addresses is not None else ["recipient@example.com"]
    email.body_plain = body_plain
    email.body_html = body_html
    email.date = date or datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc)
    email.received_at = email.date
    email.created_at = email.date
    email.is_sent = is_sent
    email.sentiment = sentiment
    email.urgency = urgency
    email.action_required = action_required
    email.security_score = security_score
    email.attachments = attachments or []
    return email


def _make_attachment(filename: str = "report.pdf", size: int | None = 1024) -> MagicMock:
    attachment = MagicMock()
    attachment.filename = filename
    attachment.size = size
    return attachment


def _make_thread(
    thread_id: int = 1,
    subject: str = "Test Thread",
    state: str = "ACTIVE",
    category: str | None = "sales",
    priority: str | None = "medium",
    security_score_avg: int | None = 85,
    summary: str | None = "Thread summary here.",
    goal: str | None = None,
    goal_status: str | None = None,
    playbook: str | None = None,
    follow_up_days: int = 3,
    next_follow_up_date: datetime | None = None,
    emails: list | None = None,
) -> MagicMock:
    thread = MagicMock()
    thread.id = thread_id
    thread.subject = subject
    thread.state = state
    thread.category = category
    thread.priority = priority
    thread.security_score_avg = security_score_avg
    thread.summary = summary
    thread.goal = goal
    thread.goal_status = goal_status
    thread.playbook = playbook
    thread.follow_up_days = follow_up_days
    thread.next_follow_up_date = next_follow_up_date
    thread.emails = emails if emails is not None else []
    return thread


# ---------------------------------------------------------------------------
# _format_size
# ---------------------------------------------------------------------------

class TestFormatSize:
    def test_formats_bytes_as_kb(self) -> None:
        from src.engine.context_writer import _format_size
        assert _format_size(2048) == "2.0 KB"

    def test_formats_large_file_as_mb(self) -> None:
        from src.engine.context_writer import _format_size
        assert _format_size(2 * 1024 * 1024) == "2.0 MB"

    def test_handles_none(self) -> None:
        from src.engine.context_writer import _format_size
        assert _format_size(None) == "unknown size"

    def test_handles_fractional_kb(self) -> None:
        from src.engine.context_writer import _format_size
        result = _format_size(512)
        assert "KB" in result

    def test_threshold_exactly_1mb(self) -> None:
        from src.engine.context_writer import _format_size
        result = _format_size(1024 * 1024)
        assert "MB" in result


# ---------------------------------------------------------------------------
# _format_addresses
# ---------------------------------------------------------------------------

class TestFormatAddresses:
    def test_formats_list(self) -> None:
        from src.engine.context_writer import _format_addresses
        result = _format_addresses(["alice@example.com", "bob@example.com"])
        assert result == "alice@example.com, bob@example.com"

    def test_formats_dict_values(self) -> None:
        from src.engine.context_writer import _format_addresses
        result = _format_addresses({"0": "alice@example.com", "1": "bob@example.com"})
        assert "alice@example.com" in result
        assert "bob@example.com" in result

    def test_returns_empty_string_for_none(self) -> None:
        from src.engine.context_writer import _format_addresses
        assert _format_addresses(None) == ""

    def test_returns_empty_string_for_empty_list(self) -> None:
        from src.engine.context_writer import _format_addresses
        assert _format_addresses([]) == ""


# ---------------------------------------------------------------------------
# _build_thread_markdown — structure tests
# ---------------------------------------------------------------------------

class TestBuildThreadMarkdownHeaders:
    def test_includes_title_with_thread_id_and_subject(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(thread_id=42, subject="Project Discussion")
        result = _build_thread_markdown(thread)
        assert "# Thread #42: Project Discussion" in result

    def test_includes_schema_version_in_frontmatter(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread()
        result = _build_thread_markdown(thread)
        assert "schema_version: 1" in result
        assert "type: thread" in result

    def test_includes_thread_id_in_frontmatter(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(thread_id=7)
        result = _build_thread_markdown(thread)
        assert "thread_id: 7" in result

    def test_includes_metadata_section(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread()
        result = _build_thread_markdown(thread)
        assert "## Metadata" in result

    def test_includes_messages_section(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread()
        result = _build_thread_markdown(thread)
        assert "## Messages" in result


class TestBuildThreadMarkdownMetadata:
    def test_always_shows_state(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(state="WAITING_REPLY")
        result = _build_thread_markdown(thread)
        assert "- **State:** WAITING_REPLY" in result

    def test_shows_category_when_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(category="support")
        result = _build_thread_markdown(thread)
        assert "- **Category:** support" in result

    def test_omits_category_when_none(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(category=None)
        result = _build_thread_markdown(thread)
        assert "**Category:**" not in result

    def test_shows_priority_when_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(priority="high")
        result = _build_thread_markdown(thread)
        assert "- **Priority:** high" in result

    def test_omits_priority_when_none(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(priority=None)
        result = _build_thread_markdown(thread)
        assert "**Priority:**" not in result

    def test_shows_security_score_when_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(security_score_avg=90)
        result = _build_thread_markdown(thread)
        assert "- **Security Score:** 90" in result

    def test_omits_security_score_when_none(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(security_score_avg=None)
        result = _build_thread_markdown(thread)
        assert "**Security Score:**" not in result

    def test_shows_goal_with_status_when_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(goal="Close the deal", goal_status="in_progress")
        result = _build_thread_markdown(thread)
        assert "- **Goal:** Close the deal [in_progress]" in result

    def test_omits_goal_when_none(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(goal=None)
        result = _build_thread_markdown(thread)
        assert "**Goal:**" not in result

    def test_shows_playbook_when_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(playbook="negotiate-price")
        result = _build_thread_markdown(thread)
        assert "- **Playbook:** negotiate-price" in result

    def test_omits_playbook_when_none(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(playbook=None)
        result = _build_thread_markdown(thread)
        assert "**Playbook:**" not in result

    def test_shows_follow_up_when_date_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        next_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        thread = _make_thread(follow_up_days=5, next_follow_up_date=next_date)
        result = _build_thread_markdown(thread)
        assert "- **Follow-up:** 5 days (next: 2026-03-01)" in result

    def test_omits_follow_up_when_no_date(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(next_follow_up_date=None)
        result = _build_thread_markdown(thread)
        assert "**Follow-up:**" not in result

    def test_always_includes_full_context_link(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread()
        result = _build_thread_markdown(thread)
        assert "- **Full context:** context/EMAIL_CONTEXT.md" in result


class TestBuildThreadMarkdownSummary:
    def test_shows_summary_when_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(summary="John proposed €7,000.")
        result = _build_thread_markdown(thread)
        assert "> John proposed €7,000." in result

    def test_shows_placeholder_when_no_summary(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(summary=None)
        result = _build_thread_markdown(thread)
        assert "> No summary available." in result


class TestBuildThreadMarkdownMessages:
    def test_single_received_email_wrapped_in_isolation_markers(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(body_plain="Please send the contract.", is_sent=False)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "=== UNTRUSTED EMAIL CONTENT START ===" in result
        assert "Please send the contract." in result
        assert "=== UNTRUSTED EMAIL CONTENT END ===" in result

    def test_sent_email_has_no_isolation_markers(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(body_plain="Here is the contract.", is_sent=True)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "=== UNTRUSTED EMAIL CONTENT START ===" not in result
        assert "Here is the contract." in result

    def test_received_email_falls_back_to_html_when_no_plain(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(body_plain=None, body_html="<p>Hello</p>", is_sent=False)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "=== UNTRUSTED EMAIL CONTENT START ===" in result
        assert "Hello" in result

    def test_direction_label_received(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(is_sent=False)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "### [1] Received:" in result

    def test_direction_label_sent(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(is_sent=True)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "### [1] Sent:" in result

    def test_emails_sorted_chronologically(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        early = _make_email(
            email_id=1,
            from_address="alice@early.example.com",
            to_addresses=["inbox@example.com"],
            date=datetime(2026, 2, 1, tzinfo=timezone.utc),
            is_sent=False,
        )
        late = _make_email(
            email_id=2,
            from_address="bob@late.example.com",
            to_addresses=["inbox@example.com"],
            date=datetime(2026, 2, 10, tzinfo=timezone.utc),
            is_sent=True,
        )
        # Pass in reverse order — function must sort them
        thread = _make_thread(emails=[late, early])
        result = _build_thread_markdown(thread)
        # Find From: lines specifically (the **From:** metadata lines in each message block)
        from_lines = [(i, line) for i, line in enumerate(result.split("\n")) if "**From:**" in line]
        assert len(from_lines) == 2
        assert "alice@early.example.com" in from_lines[0][1], (
            f"First email should be alice (early); got: {from_lines[0][1]}"
        )
        assert "bob@late.example.com" in from_lines[1][1], (
            f"Second email should be bob (late); got: {from_lines[1][1]}"
        )

    def test_body_truncated_at_max_chars(self) -> None:
        from src.engine.context_writer import _build_thread_markdown, _MAX_BODY_CHARS
        long_body = "x" * (_MAX_BODY_CHARS + 500)
        email = _make_email(body_plain=long_body, is_sent=False)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "[truncated" in result
        assert f"full body: {_MAX_BODY_CHARS + 500} chars" in result

    def test_body_not_truncated_when_under_limit(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        body = "short body"
        email = _make_email(body_plain=body, is_sent=False)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "[truncated" not in result

    def test_includes_from_address(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(from_address="alice@example.com")
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "- **From:** alice@example.com" in result

    def test_includes_to_addresses(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(to_addresses=["bob@example.com"])
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "- **To:** bob@example.com" in result

    def test_to_addresses_as_dict(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(to_addresses={"0": "carol@example.com"})
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "carol@example.com" in result


class TestBuildThreadMarkdownAttachments:
    def test_shows_attachment_section_when_present(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        attachment = _make_attachment(filename="report.pdf", size=2048)
        email = _make_email(attachments=[attachment])
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "**Attachments:**" in result
        assert "report.pdf" in result
        assert "2.0 KB" in result

    def test_omits_attachment_section_when_no_attachments(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(attachments=[])
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "**Attachments:**" not in result

    def test_formats_large_attachment_as_mb(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        attachment = _make_attachment(filename="video.mp4", size=5 * 1024 * 1024)
        email = _make_email(attachments=[attachment])
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "5.0 MB" in result


class TestBuildThreadMarkdownAnalysis:
    def test_shows_analysis_section_when_any_email_has_sentiment(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(sentiment="positive")
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "## Analysis" in result
        assert "- **Sentiment:** positive" in result

    def test_shows_analysis_when_urgency_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(urgency="high")
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "## Analysis" in result
        assert "- **Urgency:** high" in result

    def test_shows_analysis_when_action_required_set(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(action_required={"type": "reply", "by": "2026-03-01"})
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "## Analysis" in result
        assert "- **Action Required:**" in result

    def test_omits_analysis_section_when_no_analysis_data(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = _make_email(sentiment=None, urgency=None, action_required=None)
        thread = _make_thread(emails=[email])
        result = _build_thread_markdown(thread)
        assert "## Analysis" not in result

    def test_omits_analysis_for_empty_thread(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(emails=[])
        result = _build_thread_markdown(thread)
        assert "## Analysis" not in result


class TestBuildThreadMarkdownParticipants:
    def test_collects_unique_participants(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email1 = _make_email(
            from_address="alice@example.com",
            to_addresses=["bob@example.com"],
        )
        email2 = _make_email(
            from_address="bob@example.com",
            to_addresses=["alice@example.com"],
        )
        thread = _make_thread(emails=[email1, email2])
        result = _build_thread_markdown(thread)
        assert "**Participants:**" in result
        # Both participants should appear exactly once each in the list
        participants_line = [l for l in result.split("\n") if "**Participants:**" in l][0]
        assert "alice@example.com" in participants_line
        assert "bob@example.com" in participants_line


# ---------------------------------------------------------------------------
# write_single_thread_file
# ---------------------------------------------------------------------------

class TestWriteSingleThreadFile:
    @pytest.mark.asyncio
    async def test_raises_when_thread_not_found(self, tmp_path) -> None:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=scalar_result)

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", str(tmp_path / "threads")):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", str(tmp_path / "threads" / "archive")):
                    from src.engine.context_writer import write_single_thread_file
                    with pytest.raises(ValueError, match="Thread 999 not found"):
                        await write_single_thread_file(999)

    @pytest.mark.asyncio
    async def test_writes_to_threads_dir_for_active_thread(self, tmp_path) -> None:
        thread = _make_thread(thread_id=5, state="ACTIVE")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = thread
        mock_session.execute = AsyncMock(return_value=scalar_result)

        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_single_thread_file
                    path = await write_single_thread_file(5)

        assert path == os.path.join(threads_dir, "5.md")
        assert os.path.exists(path)

    @pytest.mark.asyncio
    async def test_writes_to_archive_dir_for_archived_thread(self, tmp_path) -> None:
        thread = _make_thread(thread_id=3, state="ARCHIVED")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = thread
        mock_session.execute = AsyncMock(return_value=scalar_result)

        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_single_thread_file
                    path = await write_single_thread_file(3)

        assert path == os.path.join(archive_dir, "3.md")
        assert os.path.exists(path)

    @pytest.mark.asyncio
    async def test_written_file_contains_thread_header(self, tmp_path) -> None:
        thread = _make_thread(thread_id=7, subject="Sales Inquiry", state="ACTIVE")
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = thread
        mock_session.execute = AsyncMock(return_value=scalar_result)

        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_single_thread_file
                    path = await write_single_thread_file(7)

        content = open(path).read()
        assert "# Thread #7: Sales Inquiry" in content


# ---------------------------------------------------------------------------
# write_thread_files
# ---------------------------------------------------------------------------

class TestWriteThreadFiles:
    @pytest.mark.asyncio
    async def test_writes_file_per_thread(self, tmp_path) -> None:
        threads = [
            _make_thread(thread_id=1, state="ACTIVE"),
            _make_thread(thread_id=2, state="ACTIVE"),
            _make_thread(thread_id=3, state="ARCHIVED"),
        ]
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = threads
        mock_session.execute = AsyncMock(return_value=scalars_result)

        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_thread_files
                    result_dir = await write_thread_files()

        assert result_dir == threads_dir
        assert os.path.exists(os.path.join(threads_dir, "1.md"))
        assert os.path.exists(os.path.join(threads_dir, "2.md"))
        assert os.path.exists(os.path.join(archive_dir, "3.md"))

    @pytest.mark.asyncio
    async def test_removes_orphaned_files(self, tmp_path) -> None:
        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")
        os.makedirs(threads_dir, exist_ok=True)
        os.makedirs(archive_dir, exist_ok=True)

        # Create an orphaned file for a thread that no longer exists
        orphan_path = os.path.join(threads_dir, "999.md")
        with open(orphan_path, "w") as f:
            f.write("# Thread #999: Orphan\n")

        threads = [_make_thread(thread_id=1, state="ACTIVE")]
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = threads
        mock_session.execute = AsyncMock(return_value=scalars_result)

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_thread_files
                    await write_thread_files()

        assert not os.path.exists(orphan_path), "Orphaned file should have been removed"
        assert os.path.exists(os.path.join(threads_dir, "1.md")), "Live thread file should exist"

    @pytest.mark.asyncio
    async def test_returns_threads_dir_path(self, tmp_path) -> None:
        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=scalars_result)

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_thread_files
                    result = await write_thread_files()

        assert result == threads_dir

    @pytest.mark.asyncio
    async def test_non_md_files_not_removed(self, tmp_path) -> None:
        """Files without .md extension in the threads dir must be left alone."""
        threads_dir = str(tmp_path / "threads")
        archive_dir = str(tmp_path / "threads" / "archive")
        os.makedirs(threads_dir, exist_ok=True)
        os.makedirs(archive_dir, exist_ok=True)

        readme_path = os.path.join(threads_dir, "README.txt")
        with open(readme_path, "w") as f:
            f.write("README\n")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        scalars_result = MagicMock()
        scalars_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=scalars_result)

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                    from src.engine.context_writer import write_thread_files
                    await write_thread_files()

        assert os.path.exists(readme_path), "Non-.md files must not be removed"


# ---------------------------------------------------------------------------
# write_email_context — per-thread file reference
# ---------------------------------------------------------------------------

class TestWriteEmailContextThreadReference:
    @pytest.mark.asyncio
    async def test_active_thread_reference_uses_threads_dir(self, tmp_path) -> None:
        """Each active thread entry must include a link to threads/<id>.md."""
        thread = _make_thread(thread_id=1, state="ACTIVE")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        threads_result = MagicMock()
        threads_result.scalars.return_value.all.return_value = [thread]
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[threads_result, count_result, count_result])

        context_dir = str(tmp_path / "context")
        os.makedirs(context_dir, exist_ok=True)
        threads_dir = os.path.join(context_dir, "threads")
        archive_dir = os.path.join(threads_dir, "archive")

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.CONTEXT_DIR", context_dir):
                with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                    with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                        from src.engine.context_writer import write_email_context
                        path = await write_email_context()

        content = open(path).read()
        assert "context/threads/1.md" in content

    @pytest.mark.asyncio
    async def test_archived_thread_reference_uses_archive_dir(self, tmp_path) -> None:
        """Archived thread entries must link to threads/archive/<id>.md."""
        thread = _make_thread(thread_id=2, state="ARCHIVED")
        # write_email_context only queries non-ARCHIVED threads, so patch the query
        # to return our archived thread (state filter is in the query, not the renderer)
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        threads_result = MagicMock()
        threads_result.scalars.return_value.all.return_value = [thread]
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_session.execute = AsyncMock(side_effect=[threads_result, count_result, count_result])

        context_dir = str(tmp_path / "context")
        os.makedirs(context_dir, exist_ok=True)
        threads_dir = os.path.join(context_dir, "threads")
        archive_dir = os.path.join(threads_dir, "archive")

        with patch("src.engine.context_writer.async_session", return_value=mock_session):
            with patch("src.engine.context_writer.CONTEXT_DIR", context_dir):
                with patch("src.engine.context_writer.THREADS_DIR", threads_dir):
                    with patch("src.engine.context_writer.THREADS_ARCHIVE_DIR", archive_dir):
                        from src.engine.context_writer import write_email_context
                        path = await write_email_context()

        content = open(path).read()
        assert "context/threads/archive/2.md" in content
