"""Tests for _available_actions helper in src/engine/context_writer.py.

Covers all conditional branches:
- Always-present reply commands
- State-dependent archive vs restore
- Goal-dependent set/check/mark-met commands
- Playbook-dependent suggest-playbook command
- Auto-reply mode toggle
- Integration: _build_thread_markdown includes the section
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers (minimal, matching the pattern from test_thread_files.py)
# ---------------------------------------------------------------------------

def _make_thread(
    thread_id: int = 1,
    subject: str = "Test Thread",
    state: str = "ACTIVE",
    goal: str | None = None,
    goal_status: str | None = None,
    playbook: str | None = None,
    auto_reply_mode: str | None = None,
    next_follow_up_date: datetime | None = None,
    follow_up_days: int = 3,
    emails: list | None = None,
) -> MagicMock:
    thread = MagicMock()
    thread.id = thread_id
    thread.subject = subject
    thread.state = state
    thread.category = None
    thread.priority = None
    thread.security_score_avg = None
    thread.summary = None
    thread.goal = goal
    thread.goal_status = goal_status
    thread.playbook = playbook
    thread.auto_reply_mode = auto_reply_mode
    thread.next_follow_up_date = next_follow_up_date
    thread.follow_up_days = follow_up_days
    thread.emails = emails if emails is not None else []
    return thread


def _join(lines: list[str]) -> str:
    """Join lines to a single string for substring assertions."""
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# _available_actions — always-present reply commands
# ---------------------------------------------------------------------------

class TestAvailableActionsAlwaysPresent:
    def test_section_heading_always_present(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=5)
        result = _join(_available_actions(thread))
        assert "## Available Actions" in result

    def test_reply_command_includes_thread_id(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=42)
        result = _join(_available_actions(thread))
        assert "ghostpost reply 42 --body" in result

    def test_draft_reply_command_present(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=7)
        result = _join(_available_actions(thread))
        assert "ghostpost reply 7 --body" in result
        assert "--draft" in result

    def test_both_send_and_draft_are_listed(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=1)
        lines = _available_actions(thread)
        # Both send and draft flags must appear somewhere in the output
        combined = _join(lines)
        assert "--draft" in combined
        assert "--json" in combined


# ---------------------------------------------------------------------------
# _available_actions — state-dependent (archive / restore)
# ---------------------------------------------------------------------------

class TestAvailableActionsStateDependant:
    def test_active_thread_shows_archive_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=3, state="ACTIVE")
        result = _join(_available_actions(thread))
        assert "ghostpost state 3 ARCHIVED --json" in result

    def test_archived_thread_shows_restore_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=4, state="ARCHIVED")
        result = _join(_available_actions(thread))
        assert "ghostpost state 4 ACTIVE --json" in result

    def test_active_thread_does_not_show_restore_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=3, state="ACTIVE")
        result = _join(_available_actions(thread))
        assert "ghostpost state 3 ACTIVE --json" not in result

    def test_archived_thread_does_not_show_archive_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=4, state="ARCHIVED")
        result = _join(_available_actions(thread))
        assert "ghostpost state 4 ARCHIVED --json" not in result

    def test_non_archived_state_waiting_reply_shows_archive(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=10, state="WAITING_REPLY")
        result = _join(_available_actions(thread))
        assert "ghostpost state 10 ARCHIVED --json" in result


# ---------------------------------------------------------------------------
# _available_actions — goal-dependent
# ---------------------------------------------------------------------------

class TestAvailableActionsGoalDependant:
    def test_no_goal_shows_set_goal_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=5, goal=None)
        result = _join(_available_actions(thread))
        assert f"ghostpost goal 5 --goal" in result
        assert "--criteria" in result

    def test_goal_in_progress_shows_check_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=6, goal="Close deal", goal_status="in_progress")
        result = _join(_available_actions(thread))
        assert "ghostpost goal 6 --check --json" in result

    def test_goal_in_progress_shows_mark_met_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=6, goal="Close deal", goal_status="in_progress")
        result = _join(_available_actions(thread))
        assert "ghostpost goal 6 --status met --json" in result

    def test_goal_met_does_not_show_set_goal_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=8, goal="Done", goal_status="met")
        result = _join(_available_actions(thread))
        # goal exists, status is NOT in_progress — set-goal command should not appear
        assert "--goal" not in result
        assert "--criteria" not in result

    def test_goal_met_does_not_show_check_or_status_commands(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=8, goal="Done", goal_status="met")
        result = _join(_available_actions(thread))
        assert "--check" not in result
        assert "--status met" not in result

    def test_no_goal_does_not_show_check_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=5, goal=None)
        result = _join(_available_actions(thread))
        assert "--check" not in result


# ---------------------------------------------------------------------------
# _available_actions — playbook-dependent
# ---------------------------------------------------------------------------

class TestAvailableActionsPlaybookDependant:
    def test_no_playbook_shows_apply_playbook_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=9, playbook=None)
        result = _join(_available_actions(thread))
        assert f"ghostpost apply-playbook 9 <name> --json" in result

    def test_playbook_set_omits_apply_playbook_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=11, playbook="negotiate-price")
        result = _join(_available_actions(thread))
        assert "apply-playbook" not in result


# ---------------------------------------------------------------------------
# _available_actions — auto-reply mode toggle
# ---------------------------------------------------------------------------

class TestAvailableActionsAutoReplyToggle:
    def test_auto_reply_off_shows_enable_draft_mode_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=12, auto_reply_mode="off")
        result = _join(_available_actions(thread))
        assert "ghostpost toggle 12 --mode draft --json" in result

    def test_auto_reply_none_shows_enable_draft_mode_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=13, auto_reply_mode=None)
        result = _join(_available_actions(thread))
        assert "ghostpost toggle 13 --mode draft --json" in result

    def test_auto_reply_draft_shows_disable_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=14, auto_reply_mode="draft")
        result = _join(_available_actions(thread))
        assert "ghostpost toggle 14 --mode off --json" in result

    def test_auto_reply_auto_shows_disable_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=15, auto_reply_mode="auto")
        result = _join(_available_actions(thread))
        assert "ghostpost toggle 15 --mode off --json" in result

    def test_auto_reply_off_does_not_show_disable_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=12, auto_reply_mode="off")
        result = _join(_available_actions(thread))
        assert "ghostpost toggle 12 --mode off --json" not in result

    def test_auto_reply_active_does_not_show_enable_command(self) -> None:
        from src.engine.context_writer import _available_actions
        thread = _make_thread(thread_id=14, auto_reply_mode="draft")
        result = _join(_available_actions(thread))
        assert "ghostpost toggle 14 --mode draft --json" not in result


# ---------------------------------------------------------------------------
# Integration: _build_thread_markdown includes the Available Actions section
# ---------------------------------------------------------------------------

class TestBuildThreadMarkdownAvailableActionsIntegration:
    def test_available_actions_section_present_in_markdown(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(thread_id=20)
        result = _build_thread_markdown(thread)
        assert "## Available Actions" in result

    def test_available_actions_appears_after_messages_section(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(thread_id=20)
        result = _build_thread_markdown(thread)
        messages_pos = result.find("## Messages")
        actions_pos = result.find("## Available Actions")
        assert messages_pos != -1, "## Messages section must exist"
        assert actions_pos != -1, "## Available Actions section must exist"
        assert actions_pos > messages_pos, (
            "## Available Actions must appear after ## Messages"
        )

    def test_available_actions_appears_after_analysis_when_analysis_present(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        email = MagicMock()
        email.id = 1
        email.from_address = "sender@example.com"
        email.to_addresses = ["recipient@example.com"]
        email.body_plain = "Hello"
        email.body_html = None
        email.date = datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc)
        email.received_at = email.date
        email.created_at = email.date
        email.is_sent = False
        email.sentiment = "positive"
        email.urgency = None
        email.action_required = None
        email.security_score = None
        email.attachments = []
        thread = _make_thread(thread_id=21, emails=[email])
        result = _build_thread_markdown(thread)
        analysis_pos = result.find("## Analysis")
        actions_pos = result.find("## Available Actions")
        assert analysis_pos != -1, "## Analysis section must exist"
        assert actions_pos != -1, "## Available Actions section must exist"
        assert actions_pos > analysis_pos, (
            "## Available Actions must appear after ## Analysis"
        )

    def test_reply_command_uses_correct_thread_id_in_markdown(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(thread_id=99)
        result = _build_thread_markdown(thread)
        assert "ghostpost reply 99" in result

    def test_archive_command_present_for_active_thread_in_markdown(self) -> None:
        from src.engine.context_writer import _build_thread_markdown
        thread = _make_thread(thread_id=50, state="ACTIVE")
        result = _build_thread_markdown(thread)
        assert "ghostpost state 50 ARCHIVED --json" in result
