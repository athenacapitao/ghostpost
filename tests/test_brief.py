"""Tests for src/engine/brief.py — thread brief generation."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thread(
    thread_id: int = 1,
    subject: str = "Test Thread",
    state: str = "ACTIVE",
    priority: str | None = "medium",
    security_score_avg: int | None = 90,
    category: str | None = None,
    summary: str | None = None,
    goal: str | None = None,
    acceptance_criteria: str | None = None,
    goal_status: str | None = None,
    playbook: str | None = None,
    auto_reply_mode: str = "off",
    follow_up_days: int = 3,
    next_follow_up_date: datetime | None = None,
    notes: str | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics a Thread ORM object."""
    thread = MagicMock()
    thread.id = thread_id
    thread.subject = subject
    thread.state = state
    thread.priority = priority
    thread.security_score_avg = security_score_avg
    thread.category = category
    thread.summary = summary
    thread.goal = goal
    thread.acceptance_criteria = acceptance_criteria
    thread.goal_status = goal_status
    thread.playbook = playbook
    thread.auto_reply_mode = auto_reply_mode
    thread.follow_up_days = follow_up_days
    thread.next_follow_up_date = next_follow_up_date
    thread.notes = notes
    return thread


def _make_email(
    from_address: str = "sender@example.com",
    to_addresses: list | None = None,
    body_plain: str = "Hello there",
    sentiment: str | None = "positive",
    is_sent: bool = False,
    date: datetime | None = None,
) -> MagicMock:
    email = MagicMock()
    email.from_address = from_address
    email.to_addresses = to_addresses or ["athenacapitao@gmail.com"]
    email.body_plain = body_plain
    email.sentiment = sentiment
    email.is_sent = is_sent
    email.date = date or datetime(2026, 2, 22, tzinfo=timezone.utc)
    return email


def _make_session(
    thread: object = None,
    emails: list | None = None,
    contact: object = None,
) -> AsyncMock:
    """Return a mock async context manager session with pre-wired query results.

    The implementation calls:
      - session.execute(email_query).scalars().all() — for the email list
      - session.execute(contact_query).scalar_one_or_none() — for contact lookup

    Both execute calls are wired via side_effect so the first call returns the
    email result and the second returns the contact result.
    """
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # session.get() returns the thread
    mock_session.get = AsyncMock(return_value=thread)

    # First execute call: email list — uses .scalars().all()
    email_scalars = MagicMock()
    email_scalars.all.return_value = emails or []
    email_result = MagicMock()
    email_result.scalars.return_value = email_scalars

    # Second execute call: contact lookup — uses .scalar_one_or_none() directly
    contact_result = MagicMock()
    contact_result.scalar_one_or_none.return_value = contact

    mock_session.execute = AsyncMock(side_effect=[email_result, contact_result])
    return mock_session


# ---------------------------------------------------------------------------
# generate_brief — basic structure tests
# ---------------------------------------------------------------------------

class TestGenerateBriefReturnsNone:
    @pytest.mark.asyncio
    async def test_returns_none_when_thread_not_found(self) -> None:
        mock_session = _make_session(thread=None)

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_thread_has_no_emails(self) -> None:
        thread = _make_thread()
        mock_session = _make_session(thread=thread, emails=[])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert result is None


class TestGenerateBriefCoreFields:
    @pytest.mark.asyncio
    async def test_includes_thread_id(self) -> None:
        thread = _make_thread(thread_id=42)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(42)

        assert "**Thread ID:** 42" in result

    @pytest.mark.asyncio
    async def test_includes_state(self) -> None:
        thread = _make_thread(state="WAITING_REPLY")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**State:** WAITING_REPLY" in result

    @pytest.mark.asyncio
    async def test_includes_email_count(self) -> None:
        thread = _make_thread()
        emails = [_make_email(), _make_email(from_address="other@example.com")]
        mock_session = _make_session(thread=thread, emails=emails)

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Email count:** 2" in result

    @pytest.mark.asyncio
    async def test_includes_auto_reply_mode_always(self) -> None:
        """auto_reply_mode must appear even when set to 'off'."""
        thread = _make_thread(auto_reply_mode="off")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Auto-Reply:** off" in result

    @pytest.mark.asyncio
    async def test_includes_follow_up_always(self) -> None:
        """Follow-up line must appear even when next_follow_up_date is None."""
        thread = _make_thread(follow_up_days=5, next_follow_up_date=None)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Follow-up:**" in result
        assert "5 days" in result

    @pytest.mark.asyncio
    async def test_follow_up_includes_next_date_when_set(self) -> None:
        next_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        thread = _make_thread(follow_up_days=5, next_follow_up_date=next_date)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "5 days (next: 2026-03-01)" in result


class TestGenerateBriefOptionalFields:
    @pytest.mark.asyncio
    async def test_category_shown_when_set(self) -> None:
        thread = _make_thread(category="sales")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Category:** sales" in result

    @pytest.mark.asyncio
    async def test_category_absent_when_not_set(self) -> None:
        thread = _make_thread(category=None)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Category:**" not in result

    @pytest.mark.asyncio
    async def test_summary_shown_when_set(self) -> None:
        thread = _make_thread(summary="John proposed €7,000.")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Summary:** John proposed €7,000." in result

    @pytest.mark.asyncio
    async def test_notes_shown_when_set(self) -> None:
        thread = _make_thread(notes="John has budget authority.")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Notes:** John has budget authority." in result

    @pytest.mark.asyncio
    async def test_notes_absent_when_not_set(self) -> None:
        thread = _make_thread(notes=None)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Notes:**" not in result


# ---------------------------------------------------------------------------
# Goal fields
# ---------------------------------------------------------------------------

class TestGenerateBriefGoalFields:
    @pytest.mark.asyncio
    async def test_goal_block_shown_when_goal_set(self) -> None:
        thread = _make_thread(
            goal="Negotiate price to €5,000 or below",
            acceptance_criteria="Price agreed in writing",
            goal_status="in_progress",
        )
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Goal:** Negotiate price to €5,000 or below" in result
        assert "**Acceptance Criteria:** Price agreed in writing" in result
        assert "**Goal Status:** in_progress" in result

    @pytest.mark.asyncio
    async def test_goal_block_absent_when_no_goal(self) -> None:
        thread = _make_thread(goal=None)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Goal:**" not in result
        assert "**Acceptance Criteria:**" not in result
        assert "**Goal Status:**" not in result

    @pytest.mark.asyncio
    async def test_acceptance_criteria_absent_when_not_set(self) -> None:
        thread = _make_thread(goal="win contract", acceptance_criteria=None)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Goal:** win contract" in result
        assert "**Acceptance Criteria:**" not in result


# ---------------------------------------------------------------------------
# Playbook field
# ---------------------------------------------------------------------------

class TestGenerateBriefPlaybookField:
    @pytest.mark.asyncio
    async def test_playbook_shown_when_set(self) -> None:
        thread = _make_thread(playbook="negotiate-price")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Playbook:** negotiate-price" in result

    @pytest.mark.asyncio
    async def test_playbook_absent_when_not_set(self) -> None:
        thread = _make_thread(playbook=None)
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        # The playbook metadata line should not appear (the instructions section
        # may reference it separately, but the metadata block should not)
        lines = result.split("\n")
        metadata_lines = [l for l in lines if l.startswith("- **Playbook:**")]
        assert len(metadata_lines) == 0


# ---------------------------------------------------------------------------
# Contact info
# ---------------------------------------------------------------------------

class TestGenerateBriefContactInfo:
    @pytest.mark.asyncio
    async def test_contact_shown_when_found(self) -> None:
        thread = _make_thread()
        email = _make_email()

        contact = MagicMock()
        contact.name = "John Smith"
        contact.relationship_type = "client"
        contact.preferred_style = "concise"
        contact.communication_frequency = None

        mock_session = _make_session(thread=thread, emails=[email], contact=contact)

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Contact:** John Smith. Relationship: client. Prefers concise emails" in result

    @pytest.mark.asyncio
    async def test_contact_absent_when_not_found(self) -> None:
        thread = _make_thread()
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email], contact=None)

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "**Contact:**" not in result


# ---------------------------------------------------------------------------
# _build_agent_instructions
# ---------------------------------------------------------------------------

class TestBuildAgentInstructions:
    def test_waiting_reply_state_action(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(state="WAITING_REPLY")
        result = _build_agent_instructions(thread)

        assert "## Agent Instructions" in result
        assert "Wait for reply (WAITING_REPLY state)" in result

    def test_follow_up_state_action(self) -> None:
        from src.engine.brief import _build_agent_instructions
        next_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        thread = _make_thread(state="FOLLOW_UP", next_follow_up_date=next_date)
        result = _build_agent_instructions(thread)

        assert "Overdue" in result
        assert "2026-03-01" in result

    def test_new_state_action(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(state="NEW")
        result = _build_agent_instructions(thread)

        assert "Triage this thread" in result

    def test_active_state_action(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(state="ACTIVE")
        result = _build_agent_instructions(thread)

        assert "active" in result.lower()

    def test_goal_met_state_no_follow_up_line(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(state="GOAL_MET", goal="win contract", goal_status="met")
        result = _build_agent_instructions(thread)

        # Terminal state — follow-up line should not appear
        assert "**Follow-up:**" not in result

    def test_archived_state_no_follow_up_line(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(state="ARCHIVED")
        result = _build_agent_instructions(thread)

        assert "**Follow-up:**" not in result

    def test_playbook_line_shown_when_set(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(playbook="negotiate-price")
        result = _build_agent_instructions(thread)

        assert "Follow `negotiate-price` template" in result

    def test_playbook_line_absent_when_not_set(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(playbook=None)
        result = _build_agent_instructions(thread)

        assert "**Playbook:**" not in result

    def test_auto_reply_draft_label(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(auto_reply_mode="draft")
        result = _build_agent_instructions(thread)

        assert "Create draft for approval before sending" in result

    def test_auto_reply_auto_label(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(auto_reply_mode="auto")
        result = _build_agent_instructions(thread)

        assert "Send replies automatically without approval" in result

    def test_auto_reply_off_label(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(auto_reply_mode="off")
        result = _build_agent_instructions(thread)

        assert "Do not send replies automatically" in result

    def test_goal_check_line_when_goal_in_progress(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(
            goal="price below €5,000",
            acceptance_criteria="Confirmed in writing",
            goal_status="in_progress",
        )
        result = _build_agent_instructions(thread)

        assert "**Goal check:**" in result
        assert "Confirmed in writing" in result

    def test_goal_check_absent_when_no_goal(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(goal=None, goal_status=None)
        result = _build_agent_instructions(thread)

        assert "**Goal check:**" not in result

    def test_goal_check_met_message_when_goal_met(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(goal="close deal", goal_status="met")
        result = _build_agent_instructions(thread)

        assert "Goal already met" in result

    def test_follow_up_scheduled_when_date_set(self) -> None:
        from src.engine.brief import _build_agent_instructions
        next_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        thread = _make_thread(
            state="WAITING_REPLY",
            next_follow_up_date=next_date,
        )
        result = _build_agent_instructions(thread)

        assert "If no reply by 2026-03-01" in result

    def test_follow_up_cadence_when_no_date_set(self) -> None:
        from src.engine.brief import _build_agent_instructions
        thread = _make_thread(state="ACTIVE", next_follow_up_date=None, follow_up_days=7)
        result = _build_agent_instructions(thread)

        assert "7 days" in result


# ---------------------------------------------------------------------------
# Integration: agent instructions section appears in full brief
# ---------------------------------------------------------------------------

class TestGenerateBriefAgentInstructionsSection:
    @pytest.mark.asyncio
    async def test_agent_instructions_section_present(self) -> None:
        thread = _make_thread(state="WAITING_REPLY")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        assert "## Agent Instructions" in result

    @pytest.mark.asyncio
    async def test_agent_instructions_section_is_last(self) -> None:
        """Agent Instructions section must be at the end of the brief."""
        thread = _make_thread(state="ACTIVE", notes="some note")
        email = _make_email()
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(1)

        instructions_pos = result.index("## Agent Instructions")
        notes_pos = result.index("**Notes:**")
        assert instructions_pos > notes_pos

    @pytest.mark.asyncio
    async def test_full_brief_field_order(self) -> None:
        """Verify the key fields appear in the documented order."""
        next_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        thread = _make_thread(
            thread_id=42,
            subject="Project Pricing Discussion",
            state="WAITING_REPLY",
            priority="high",
            security_score_avg=95,
            category="sales",
            summary="John proposed €7,000. You countered at €4,500.",
            goal="Negotiate price to €5,000 or below",
            acceptance_criteria="Price agreed in writing",
            goal_status="in_progress",
            playbook="negotiate-price",
            auto_reply_mode="draft",
            follow_up_days=5,
            next_follow_up_date=next_date,
            notes="John has budget authority.",
        )
        email = _make_email(body_plain="Let me discuss with my team.")
        mock_session = _make_session(thread=thread, emails=[email])

        with patch("src.engine.brief.async_session", return_value=mock_session):
            from src.engine.brief import generate_brief
            result = await generate_brief(42)

        # Verify all documented fields are present
        assert "**Thread ID:** 42" in result
        assert "**State:** WAITING_REPLY" in result
        assert "**Category:** sales" in result
        assert "**Summary:** John proposed €7,000." in result
        assert "**Goal:** Negotiate price to €5,000 or below" in result
        assert "**Acceptance Criteria:** Price agreed in writing" in result
        assert "**Goal Status:** in_progress" in result
        assert "**Playbook:** negotiate-price" in result
        assert "**Auto-Reply:** draft" in result
        assert "5 days (next: 2026-03-01)" in result
        assert "## Agent Instructions" in result

        # Verify the relative order of key sections
        summary_pos = result.index("**Summary:**")
        goal_pos = result.index("**Goal:**")
        playbook_pos = result.index("**Playbook:**")
        auto_reply_pos = result.index("**Auto-Reply:**")
        last_msg_pos = result.index("**Last message:**")
        instructions_pos = result.index("## Agent Instructions")

        assert summary_pos < goal_pos < playbook_pos < auto_reply_pos
        assert auto_reply_pos < last_msg_pos < instructions_pos
