"""Tests for write_system_brief() in src/engine/context_writer.py.

Strategy:
- Unit tests: mock async_session and all DB queries, verify output structure and
  content without touching the real database or filesystem (using tmp_path).
- One smoke test: patch _atomic_write to avoid real disk writes, verify the
  function runs end-to-end without error.
"""

import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thread(
    thread_id: int = 1,
    subject: str = "Test Subject",
    state: str = "ACTIVE",
    priority: str | None = "high",
    goal: str | None = None,
    goal_status: str | None = None,
    next_follow_up_date: datetime | None = None,
    emails: list | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics a Thread ORM object."""
    thread = MagicMock()
    thread.id = thread_id
    thread.subject = subject
    thread.state = state
    thread.priority = priority
    thread.goal = goal
    thread.goal_status = goal_status
    thread.next_follow_up_date = next_follow_up_date
    thread.emails = emails or []
    return thread


def _make_email(from_address: str = "sender@example.com", is_sent: bool = False) -> MagicMock:
    email = MagicMock()
    email.from_address = from_address
    email.is_sent = is_sent
    email.to_addresses = ["recipient@example.com"]
    return email


def _make_scalar_result(value) -> MagicMock:
    """Return a MagicMock whose .scalar() returns the given value."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_scalars_result(items: list) -> MagicMock:
    """Return a MagicMock whose .scalars().all() returns items."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _make_all_result(rows: list) -> MagicMock:
    """Return a MagicMock whose .all() returns rows (for group_by queries)."""
    result = MagicMock()
    result.all.return_value = rows
    return result


# ---------------------------------------------------------------------------
# Fixture: patch async_session and CONTEXT_DIR
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session_ctx(tmp_path):
    """Yields (session_mock, tmp_context_dir).

    Patches:
    - async_session so no real DB is touched
    - CONTEXT_DIR so files are written to tmp_path, not production context/
    """
    session_mock = AsyncMock()

    # Default responses — all queries return empty/zero
    # The execute() side_effect list drives each successive await session.execute() call.
    session_mock.execute = AsyncMock(return_value=_make_scalar_result(0))

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)

    context_dir = str(tmp_path / "context")
    os.makedirs(context_dir, exist_ok=True)

    with patch("src.engine.context_writer.async_session", return_value=cm):
        with patch("src.engine.context_writer.CONTEXT_DIR", context_dir):
            yield session_mock, context_dir


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_system_brief_creates_file(mock_session_ctx):
    """The function must create SYSTEM_BRIEF.md in CONTEXT_DIR."""
    session_mock, context_dir = mock_session_ctx

    # Provide minimal execute responses (one per await session.execute() call)
    # Order: state_counts, unread, pending_drafts, last_sync,
    #        attention_threads, active_goals,
    #        pending_alerts, quarantined,
    #        emails_received, emails_sent, drafts_created, drafts_approved
    responses = [
        _make_all_result([]),          # state_counts group_by
        _make_scalar_result(0),        # unread
        _make_scalar_result(0),        # pending_drafts
        _make_scalar_result(None),     # last_sync (max received_at)
        _make_scalars_result([]),      # attention_threads
        _make_scalars_result([]),      # active_goals
        _make_scalar_result(0),        # pending_alerts
        _make_scalar_result(0),        # quarantined
        _make_scalar_result(0),        # emails_received_24h
        _make_scalar_result(0),        # emails_sent_24h
        _make_scalar_result(0),        # drafts_created_24h
        _make_scalar_result(0),        # drafts_approved_24h
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()

    assert os.path.exists(path), "SYSTEM_BRIEF.md was not created"
    assert path.endswith("SYSTEM_BRIEF.md")


@pytest.mark.asyncio
async def test_write_system_brief_header_content(mock_session_ctx):
    """Output must contain required header elements."""
    session_mock, context_dir = mock_session_ctx

    responses = [
        _make_all_result([("NEW", 5), ("ACTIVE", 3), ("ARCHIVED", 10)]),
        _make_scalar_result(7),        # unread
        _make_scalar_result(2),        # pending_drafts
        _make_scalar_result(
            datetime(2026, 2, 25, 12, 0, 0, tzinfo=timezone.utc)
        ),                             # last_sync
        _make_scalars_result([]),      # attention_threads
        _make_scalars_result([]),      # active_goals
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(4),        # emails_received_24h
        _make_scalar_result(1),        # emails_sent_24h
        _make_scalar_result(3),        # drafts_created_24h
        _make_scalar_result(1),        # drafts_approved_24h
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "# System Brief" in content
    assert "schema_version: 1" in content
    assert "type: system_brief" in content
    assert "## Status" in content
    assert "Last Sync: 2026-02-25 12:00 UTC" in content
    assert "## Inbox" in content
    assert "Threads: 18" in content   # 5 + 3 + 10
    assert "Unread: 7" in content
    assert "Drafts Pending: 2" in content
    assert "NEW(5)" in content
    assert "ACTIVE(3)" in content
    assert "ARCHIVED(10)" in content
    assert "## Needs Attention" in content
    assert "## Active Goals (0)" in content
    assert "## Security" in content
    assert "## Recent Activity (last 24h)" in content
    assert "4 emails received, 1 sent" in content
    assert "3 drafts created, 1 approved" in content


@pytest.mark.asyncio
async def test_write_system_brief_last_sync_never(mock_session_ctx):
    """When no emails exist, last sync should display as 'never'."""
    session_mock, context_dir = mock_session_ctx

    responses = [
        _make_all_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),     # no emails in DB -> last sync = never
        _make_scalars_result([]),
        _make_scalars_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "Last Sync: never" in content


@pytest.mark.asyncio
async def test_write_system_brief_attention_items_appear(mock_session_ctx):
    """High-priority and overdue threads should appear in the Needs Attention table."""
    session_mock, context_dir = mock_session_ctx

    now = datetime.now(timezone.utc)
    overdue_date = now - timedelta(days=2)

    high_thread = _make_thread(
        thread_id=42,
        subject="Important Deal Closing",
        priority="high",
        next_follow_up_date=None,
        emails=[_make_email("alice@example.com")],
    )
    overdue_thread = _make_thread(
        thread_id=99,
        subject="Pending Response Needed",
        priority="medium",
        next_follow_up_date=overdue_date,
        emails=[_make_email("bob@example.com")],
    )

    responses = [
        _make_all_result([("NEW", 2)]),
        _make_scalar_result(3),
        _make_scalar_result(1),
        _make_scalar_result(None),
        _make_scalars_result([high_thread, overdue_thread]),   # attention threads
        _make_scalars_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "#42" in content
    assert "Important Deal Closing" in content
    assert "HIGH priority" in content
    assert "alice@example.com" in content

    assert "#99" in content
    assert "Pending Response Needed" in content
    assert "overdue follow-up" in content
    assert "bob@example.com" in content


@pytest.mark.asyncio
async def test_write_system_brief_no_attention_items_placeholder(mock_session_ctx):
    """When no threads need attention, a placeholder row must appear."""
    session_mock, context_dir = mock_session_ctx

    responses = [
        _make_all_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),
        _make_scalars_result([]),      # no attention threads
        _make_scalars_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "No items need immediate attention" in content


@pytest.mark.asyncio
async def test_write_system_brief_active_goals_appear(mock_session_ctx):
    """In-progress goals must appear in the Active Goals table."""
    session_mock, context_dir = mock_session_ctx

    goal_thread = _make_thread(
        thread_id=7,
        subject="Partnership Negotiation",
        goal="Secure partnership agreement by Q2",
        goal_status="in_progress",
        emails=[],
    )

    responses = [
        _make_all_result([("ACTIVE", 1)]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),
        _make_scalars_result([]),
        _make_scalars_result([goal_thread]),   # active goals
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "## Active Goals (1)" in content
    assert "#7" in content
    assert "Secure partnership agreement by Q2" in content
    assert "in_progress" in content


@pytest.mark.asyncio
async def test_write_system_brief_no_goals_placeholder(mock_session_ctx):
    """When no active goals exist, a placeholder row must appear."""
    session_mock, context_dir = mock_session_ctx

    responses = [
        _make_all_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),
        _make_scalars_result([]),
        _make_scalars_result([]),      # no active goals
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "No active goals" in content


@pytest.mark.asyncio
async def test_write_system_brief_security_counts(mock_session_ctx):
    """Pending alert and quarantine counts must appear in the Security section."""
    session_mock, context_dir = mock_session_ctx

    responses = [
        _make_all_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),
        _make_scalars_result([]),
        _make_scalars_result([]),
        _make_scalar_result(3),        # pending_alerts
        _make_scalar_result(1),        # quarantined
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    assert "Pending alerts: 3" in content
    assert "Quarantined: 1" in content


@pytest.mark.asyncio
async def test_write_system_brief_uses_atomic_write(mock_session_ctx):
    """_atomic_write must be called (not plain open) for safe concurrent reads."""
    session_mock, context_dir = mock_session_ctx

    responses = [
        _make_all_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),
        _make_scalars_result([]),
        _make_scalars_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    with patch("src.engine.context_writer._atomic_write") as mock_aw:
        from src.engine.context_writer import write_system_brief

        path = await write_system_brief()

        mock_aw.assert_called_once()
        called_path = mock_aw.call_args[0][0]
        assert called_path.endswith("SYSTEM_BRIEF.md")


@pytest.mark.asyncio
async def test_write_all_context_files_calls_system_brief_first(mock_session_ctx):
    """write_all_context_files must invoke write_system_brief before other writers."""
    session_mock, _ = mock_session_ctx

    call_order: list[str] = []

    async def _fake_brief():
        call_order.append("system_brief")
        return "/fake/SYSTEM_BRIEF.md"

    async def _fake_email():
        call_order.append("email_context")
        return "/fake/EMAIL_CONTEXT.md"

    async def _fake_contacts():
        call_order.append("contacts")
        return "/fake/CONTACTS.md"

    async def _fake_rules():
        call_order.append("rules")
        return "/fake/RULES.md"

    async def _fake_goals():
        call_order.append("active_goals")
        return "/fake/ACTIVE_GOALS.md"

    async def _fake_drafts():
        call_order.append("drafts")
        return "/fake/DRAFTS.md"

    async def _fake_security():
        call_order.append("security_alerts")
        return "/fake/SECURITY_ALERTS.md"

    async def _fake_thread_files():
        call_order.append("thread_files")
        return "/fake/context/threads"

    async def _fake_research():
        call_order.append("research_context")
        return "/fake/RESEARCH.md"

    async def _fake_outcomes():
        call_order.append("completed_outcomes")
        return "/fake/COMPLETED_OUTCOMES.md"

    with patch("src.engine.context_writer.write_system_brief", side_effect=_fake_brief):
        with patch("src.engine.context_writer.write_email_context", side_effect=_fake_email):
            with patch("src.engine.context_writer.write_thread_files", side_effect=_fake_thread_files):
                with patch("src.engine.context_writer.write_contacts", side_effect=_fake_contacts):
                    with patch("src.engine.context_writer.write_rules", side_effect=_fake_rules):
                        with patch("src.engine.context_writer.write_active_goals", side_effect=_fake_goals):
                            with patch("src.engine.context_writer.write_drafts", side_effect=_fake_drafts):
                                with patch("src.engine.context_writer.write_security_alerts", side_effect=_fake_security):
                                    with patch("src.engine.context_writer.write_research_context", side_effect=_fake_research):
                                        with patch("src.engine.context_writer.write_completed_outcomes", side_effect=_fake_outcomes):
                                            from src.engine.context_writer import write_all_context_files

                                            paths = await write_all_context_files()

    assert call_order[0] == "system_brief", (
        f"write_system_brief must be first; got order: {call_order}"
    )
    assert len(paths) == 10
    # write_thread_files must run immediately after write_email_context so that
    # the per-thread files exist before the context refresh completes
    assert call_order == [
        "system_brief",
        "email_context",
        "thread_files",
        "contacts",
        "rules",
        "active_goals",
        "drafts",
        "security_alerts",
        "research_context",
        "completed_outcomes",
    ]


@pytest.mark.asyncio
async def test_write_system_brief_goal_truncated_at_60_chars(mock_session_ctx):
    """Goals longer than 60 characters must be truncated in the table."""
    session_mock, context_dir = mock_session_ctx

    long_goal = "A" * 80
    goal_thread = _make_thread(
        thread_id=5,
        goal=long_goal,
        goal_status="in_progress",
        emails=[],
    )

    responses = [
        _make_all_result([]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(None),
        _make_scalars_result([]),
        _make_scalars_result([goal_thread]),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
        _make_scalar_result(0),
    ]
    session_mock.execute = AsyncMock(side_effect=responses)

    from src.engine.context_writer import write_system_brief

    path = await write_system_brief()
    content = open(path).read()

    # The full 80-char string must NOT appear verbatim in the file
    assert long_goal not in content
    # The 60-char truncation must appear
    assert "A" * 60 in content
