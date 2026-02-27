"""Tests for src/engine/triage.py — triage snapshot generation."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thread(
    thread_id: int = 1,
    subject: str = "Test Thread",
    state: str = "ACTIVE",
    priority: str | None = "medium",
    goal: str | None = None,
    goal_status: str | None = None,
    next_follow_up_date: datetime | None = None,
    updated_at: datetime | None = None,
    last_activity_at: datetime | None = None,
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
    thread.updated_at = updated_at
    thread.last_activity_at = last_activity_at
    return thread


def _make_draft(
    draft_id: int = 1,
    thread_id: int = 1,
    subject: str = "Re: Test",
    status: str = "pending",
    created_at: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics a Draft ORM object."""
    draft = MagicMock()
    draft.id = draft_id
    draft.thread_id = thread_id
    draft.subject = subject
    draft.status = status
    draft.created_at = created_at or datetime.now(timezone.utc)
    return draft


def _make_security_event(
    event_id: int = 1,
    severity: str = "high",
    event_type: str = "injection_detected",
    thread_id: int | None = 5,
    resolution: str = "pending",
) -> MagicMock:
    """Build a MagicMock that mimics a SecurityEvent ORM object."""
    ev = MagicMock()
    ev.id = event_id
    ev.severity = severity
    ev.event_type = event_type
    ev.thread_id = thread_id
    ev.resolution = resolution
    return ev


def _make_mock_session(
    state_rows: list | None = None,
    unread_count: int = 0,
    drafts: list | None = None,
    sec_events: list | None = None,
    overdue: list | None = None,
    new_threads: list | None = None,
    goal_threads: list | None = None,
) -> AsyncMock:
    """Wire up a mock session with the multi-execute call sequence used by get_triage_data.

    get_triage_data fires these execute calls in order:
      1. state counts (group by)
      2. unread count
      3. pending drafts
      4. pending security events
      5. overdue follow-up threads
      6. NEW threads
      7. in-progress goal threads
    """
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    def _scalars_result(items: list) -> MagicMock:
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = items
        result = MagicMock()
        result.scalars.return_value = scalars_mock
        return result

    def _scalar_result(value) -> MagicMock:
        result = MagicMock()
        result.scalar.return_value = value
        return result

    # Positional execute call results matching the query order in get_triage_data
    state_result = MagicMock()
    state_result.all.return_value = state_rows or []

    execute_results = [
        state_result,                                # state counts
        _scalar_result(unread_count),                # unread count
        _scalars_result(drafts or []),               # pending drafts
        _scalars_result(sec_events or []),           # security events
        _scalars_result(overdue or []),              # overdue threads
        _scalars_result(new_threads or []),          # NEW threads
        _scalars_result(goal_threads or []),         # goal threads
    ]

    mock_session.execute = AsyncMock(side_effect=execute_results)
    return mock_session


# ---------------------------------------------------------------------------
# TriageSnapshot.to_dict
# ---------------------------------------------------------------------------

class TestTriageSnapshotToDict:
    def test_to_dict_returns_dict(self) -> None:
        from src.engine.triage import TriageSnapshot
        snapshot = TriageSnapshot(timestamp="2026-02-25T12:00:00Z")
        result = snapshot.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_timestamp(self) -> None:
        from src.engine.triage import TriageSnapshot
        snapshot = TriageSnapshot(timestamp="2026-02-25T12:00:00Z")
        assert snapshot.to_dict()["timestamp"] == "2026-02-25T12:00:00Z"

    def test_to_dict_contains_all_keys(self) -> None:
        from src.engine.triage import TriageSnapshot
        snapshot = TriageSnapshot(timestamp="2026-02-25T12:00:00Z")
        d = snapshot.to_dict()
        assert set(d.keys()) == {
            "timestamp", "summary", "actions",
            "overdue_threads", "pending_drafts",
            "security_incidents", "new_threads",
        }


# ---------------------------------------------------------------------------
# TriageAction scoring and serialisation
# ---------------------------------------------------------------------------

class TestTriageAction:
    def test_action_score_defaults_to_zero(self) -> None:
        from src.engine.triage import TriageAction
        action = TriageAction(
            action="review_new",
            target_type="thread",
            target_id=1,
            reason="New thread",
            priority="low",
            command="ghostpost brief 1 --json",
        )
        assert action.score == 0

    def test_action_score_can_be_set(self) -> None:
        from src.engine.triage import TriageAction
        action = TriageAction(
            action="review_security",
            target_type="security_event",
            target_id=1,
            reason="CRITICAL injection_detected",
            priority="critical",
            command="ghostpost quarantine list --json",
            score=100,
        )
        assert action.score == 100


# ---------------------------------------------------------------------------
# get_triage_data — summary fields
# ---------------------------------------------------------------------------

class TestGetTriageDataSummary:
    @pytest.mark.asyncio
    async def test_summary_total_threads(self) -> None:
        state_rows = [("NEW", 3), ("ACTIVE", 5)]
        mock_session = _make_mock_session(state_rows=state_rows, unread_count=2)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["total_threads"] == 8

    @pytest.mark.asyncio
    async def test_summary_unread_count(self) -> None:
        mock_session = _make_mock_session(unread_count=7)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["unread"] == 7

    @pytest.mark.asyncio
    async def test_summary_pending_drafts_count(self) -> None:
        drafts = [_make_draft(draft_id=1), _make_draft(draft_id=2)]
        mock_session = _make_mock_session(drafts=drafts)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["pending_drafts"] == 2

    @pytest.mark.asyncio
    async def test_summary_security_incidents_count(self) -> None:
        events = [_make_security_event(event_id=1), _make_security_event(event_id=2)]
        mock_session = _make_mock_session(sec_events=events)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["security_incidents"] == 2

    @pytest.mark.asyncio
    async def test_summary_overdue_threads_count(self) -> None:
        now = datetime.now(timezone.utc)
        overdue = [_make_thread(state="FOLLOW_UP", next_follow_up_date=now - timedelta(days=2))]
        mock_session = _make_mock_session(overdue=overdue)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["overdue_threads"] == 1

    @pytest.mark.asyncio
    async def test_summary_new_threads_count(self) -> None:
        new_threads = [_make_thread(state="NEW"), _make_thread(thread_id=2, state="NEW")]
        mock_session = _make_mock_session(new_threads=new_threads)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["new_threads"] == 2

    @pytest.mark.asyncio
    async def test_summary_by_state_mapping(self) -> None:
        state_rows = [("NEW", 4), ("ACTIVE", 2), ("ARCHIVED", 10)]
        mock_session = _make_mock_session(state_rows=state_rows)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.summary["by_state"] == {"NEW": 4, "ACTIVE": 2, "ARCHIVED": 10}


# ---------------------------------------------------------------------------
# get_triage_data — action generation and scoring
# ---------------------------------------------------------------------------

class TestGetTriageDataActions:
    @pytest.mark.asyncio
    async def test_security_event_critical_gets_score_100(self) -> None:
        ev = _make_security_event(severity="critical")
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        actions = snapshot.actions
        security_actions = [a for a in actions if a["action"] == "review_security"]
        assert security_actions, "Expected at least one review_security action"
        assert security_actions[0]["score"] == 100

    @pytest.mark.asyncio
    async def test_security_event_high_gets_score_80(self) -> None:
        ev = _make_security_event(severity="high")
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        security_actions = [a for a in snapshot.actions if a["action"] == "review_security"]
        assert security_actions[0]["score"] == 80

    @pytest.mark.asyncio
    async def test_security_event_medium_gets_score_40(self) -> None:
        ev = _make_security_event(severity="medium")
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        security_actions = [a for a in snapshot.actions if a["action"] == "review_security"]
        assert security_actions[0]["score"] == 40

    @pytest.mark.asyncio
    async def test_old_draft_gets_score_60(self) -> None:
        old_time = datetime.now(timezone.utc) - timedelta(hours=4)
        draft = _make_draft(created_at=old_time)
        mock_session = _make_mock_session(drafts=[draft])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        draft_actions = [a for a in snapshot.actions if a["action"] == "approve_draft"]
        assert draft_actions[0]["score"] == 60

    @pytest.mark.asyncio
    async def test_new_draft_gets_score_35(self) -> None:
        draft = _make_draft(created_at=datetime.now(timezone.utc))
        mock_session = _make_mock_session(drafts=[draft])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        draft_actions = [a for a in snapshot.actions if a["action"] == "approve_draft"]
        assert draft_actions[0]["score"] == 35

    @pytest.mark.asyncio
    async def test_very_overdue_thread_gets_score_50(self) -> None:
        long_ago = datetime.now(timezone.utc) - timedelta(days=5)
        thread = _make_thread(state="FOLLOW_UP", next_follow_up_date=long_ago)
        mock_session = _make_mock_session(overdue=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        overdue_actions = [a for a in snapshot.actions if a["action"] == "follow_up"]
        assert overdue_actions[0]["score"] == 50

    @pytest.mark.asyncio
    async def test_recently_overdue_thread_gets_score_30(self) -> None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        thread = _make_thread(state="WAITING_REPLY", next_follow_up_date=yesterday)
        mock_session = _make_mock_session(overdue=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        overdue_actions = [a for a in snapshot.actions if a["action"] == "follow_up"]
        assert overdue_actions[0]["score"] == 30

    @pytest.mark.asyncio
    async def test_high_priority_new_thread_gets_score_40(self) -> None:
        thread = _make_thread(state="NEW", priority="high")
        mock_session = _make_mock_session(new_threads=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        new_actions = [a for a in snapshot.actions if a["action"] == "review_new"]
        assert new_actions[0]["score"] == 40

    @pytest.mark.asyncio
    async def test_low_priority_new_thread_gets_score_15(self) -> None:
        thread = _make_thread(state="NEW", priority="low")
        mock_session = _make_mock_session(new_threads=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        new_actions = [a for a in snapshot.actions if a["action"] == "review_new"]
        assert new_actions[0]["score"] == 15

    @pytest.mark.asyncio
    async def test_goal_thread_gets_score_20(self) -> None:
        thread = _make_thread(state="ACTIVE", goal="close deal", goal_status="in_progress")
        mock_session = _make_mock_session(goal_threads=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        goal_actions = [a for a in snapshot.actions if a["action"] == "check_goal"]
        assert goal_actions[0]["score"] == 20


# ---------------------------------------------------------------------------
# get_triage_data — action ordering
# ---------------------------------------------------------------------------

class TestGetTriageDataActionOrdering:
    @pytest.mark.asyncio
    async def test_actions_sorted_by_score_descending(self) -> None:
        """Critical security event must appear before a low-priority new thread."""
        ev = _make_security_event(severity="critical")
        new_thread = _make_thread(state="NEW", priority="low")
        mock_session = _make_mock_session(sec_events=[ev], new_threads=[new_thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert len(snapshot.actions) >= 2
        scores = [a["score"] for a in snapshot.actions]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_limit_caps_actions(self) -> None:
        events = [_make_security_event(event_id=i) for i in range(5)]
        mock_session = _make_mock_session(sec_events=events)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data(limit=3)

        assert len(snapshot.actions) <= 3

    @pytest.mark.asyncio
    async def test_default_limit_is_ten(self) -> None:
        events = [_make_security_event(event_id=i) for i in range(15)]
        mock_session = _make_mock_session(sec_events=events)

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert len(snapshot.actions) <= 10


# ---------------------------------------------------------------------------
# get_triage_data — action fields
# ---------------------------------------------------------------------------

class TestGetTriageDataActionFields:
    @pytest.mark.asyncio
    async def test_security_action_command_points_to_quarantine(self) -> None:
        ev = _make_security_event(severity="high")
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        security_actions = [a for a in snapshot.actions if a["action"] == "review_security"]
        assert "quarantine" in security_actions[0]["command"]

    @pytest.mark.asyncio
    async def test_draft_action_command_contains_draft_id(self) -> None:
        draft = _make_draft(draft_id=42)
        mock_session = _make_mock_session(drafts=[draft])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        draft_actions = [a for a in snapshot.actions if a["action"] == "approve_draft"]
        assert "42" in draft_actions[0]["command"]

    @pytest.mark.asyncio
    async def test_new_thread_action_command_contains_brief(self) -> None:
        thread = _make_thread(thread_id=99, state="NEW")
        mock_session = _make_mock_session(new_threads=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        new_actions = [a for a in snapshot.actions if a["action"] == "review_new"]
        assert "brief" in new_actions[0]["command"]
        assert "99" in new_actions[0]["command"]

    @pytest.mark.asyncio
    async def test_security_event_with_no_thread_reason_has_no_hash(self) -> None:
        ev = _make_security_event(severity="high", thread_id=None)
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        security_actions = [a for a in snapshot.actions if a["action"] == "review_security"]
        reason = security_actions[0]["reason"]
        assert "thread" not in reason.lower()

    @pytest.mark.asyncio
    async def test_security_event_with_thread_reason_includes_thread_ref(self) -> None:
        ev = _make_security_event(severity="high", thread_id=7)
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        security_actions = [a for a in snapshot.actions if a["action"] == "review_security"]
        reason = security_actions[0]["reason"]
        assert "thread #7" in reason


# ---------------------------------------------------------------------------
# get_triage_data — list fields in snapshot
# ---------------------------------------------------------------------------

class TestGetTriageDataListFields:
    @pytest.mark.asyncio
    async def test_pending_drafts_list_contains_id_and_subject(self) -> None:
        draft = _make_draft(draft_id=5, subject="Re: Important Deal")
        mock_session = _make_mock_session(drafts=[draft])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert len(snapshot.pending_drafts) == 1
        assert snapshot.pending_drafts[0]["id"] == 5
        assert "Important Deal" in snapshot.pending_drafts[0]["subject"]

    @pytest.mark.asyncio
    async def test_security_incidents_list_contains_severity(self) -> None:
        ev = _make_security_event(event_id=3, severity="critical")
        mock_session = _make_mock_session(sec_events=[ev])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert len(snapshot.security_incidents) == 1
        assert snapshot.security_incidents[0]["severity"] == "critical"
        assert snapshot.security_incidents[0]["id"] == 3

    @pytest.mark.asyncio
    async def test_new_threads_list_contains_priority(self) -> None:
        thread = _make_thread(thread_id=11, state="NEW", priority="high")
        mock_session = _make_mock_session(new_threads=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert len(snapshot.new_threads) == 1
        assert snapshot.new_threads[0]["priority"] == "high"
        assert snapshot.new_threads[0]["id"] == 11

    @pytest.mark.asyncio
    async def test_overdue_threads_list_contains_days_overdue(self) -> None:
        overdue_date = datetime.now(timezone.utc) - timedelta(days=4)
        thread = _make_thread(state="FOLLOW_UP", next_follow_up_date=overdue_date)
        mock_session = _make_mock_session(overdue=[thread])

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert len(snapshot.overdue_threads) == 1
        assert snapshot.overdue_threads[0]["days_overdue"] == 4

    @pytest.mark.asyncio
    async def test_empty_inbox_produces_no_actions(self) -> None:
        mock_session = _make_mock_session()

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        assert snapshot.actions == []
        assert snapshot.summary["total_threads"] == 0


# ---------------------------------------------------------------------------
# get_triage_data — timestamp format
# ---------------------------------------------------------------------------

class TestGetTriageDataTimestamp:
    @pytest.mark.asyncio
    async def test_timestamp_is_iso_format(self) -> None:
        mock_session = _make_mock_session()

        with patch("src.engine.triage.async_session", return_value=mock_session):
            from src.engine.triage import get_triage_data
            snapshot = await get_triage_data()

        # Must parse as a datetime without raising
        parsed = datetime.strptime(snapshot.timestamp, "%Y-%m-%dT%H:%M:%SZ")
        assert parsed.year >= 2026
