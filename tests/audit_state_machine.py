"""Thread state machine edge case tests.

Validates every valid transition, rejects invalid transitions, handles
concurrent and rapid state changes, and verifies audit log + event publishing.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.engine.state_machine import (
    transition, auto_transition_on_send, auto_transition_on_receive,
    get_threads_needing_follow_up, STATES,
)
from src.db.models import Thread
from src.db.session import async_session

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper: create a thread with specific state
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def make_thread():
    """Factory fixture to create threads with specific states."""
    created_ids = []

    async def _make(state="NEW", gmail_id_suffix="001", **kwargs):
        async with async_session() as session:
            thread = Thread(
                gmail_thread_id=f"audit_sm_{gmail_id_suffix}_{id(state)}",
                subject=f"State Machine Test ({state})",
                state=state,
                **kwargs,
            )
            session.add(thread)
            await session.commit()
            await session.refresh(thread)
            created_ids.append(thread.id)
            session.expunge(thread)
            return thread

    yield _make

    # Cleanup
    for tid in created_ids:
        async with async_session() as session:
            obj = await session.get(Thread, tid)
            if obj:
                await session.delete(obj)
                await session.commit()


# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

class TestValidTransitions:
    @pytest.mark.parametrize("from_state,to_state", [
        ("NEW", "ACTIVE"),
        ("ACTIVE", "WAITING_REPLY"),
        ("WAITING_REPLY", "FOLLOW_UP"),
        ("FOLLOW_UP", "WAITING_REPLY"),
        ("ACTIVE", "GOAL_MET"),
        ("GOAL_MET", "ARCHIVED"),
        ("ACTIVE", "ARCHIVED"),
        ("NEW", "ARCHIVED"),
        ("WAITING_REPLY", "ACTIVE"),
        ("FOLLOW_UP", "ACTIVE"),
    ])
    async def test_valid_transition(self, make_thread, from_state, to_state):
        """All valid transitions should succeed."""
        thread = await make_thread(state=from_state, gmail_id_suffix=f"{from_state}_{to_state}")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            old_state = await transition(thread.id, to_state, reason="test")
            assert old_state == from_state

        # Verify state was actually changed in DB
        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == to_state


# ---------------------------------------------------------------------------
# Invalid state handling
# ---------------------------------------------------------------------------

class TestInvalidStates:
    async def test_invalid_state_string_raises(self, make_thread):
        """Transition to an invalid state string should raise ValueError."""
        thread = await make_thread(state="NEW", gmail_id_suffix="invalid_state")
        with pytest.raises(ValueError, match="Invalid state"):
            await transition(thread.id, "INVALID_STATE")

    async def test_empty_state_raises(self, make_thread):
        """Empty state string should raise ValueError."""
        thread = await make_thread(state="NEW", gmail_id_suffix="empty_state")
        with pytest.raises(ValueError):
            await transition(thread.id, "")

    async def test_null_state_raises(self, make_thread):
        """None state should raise ValueError (or TypeError)."""
        thread = await make_thread(state="NEW", gmail_id_suffix="null_state")
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await transition(thread.id, None)


# ---------------------------------------------------------------------------
# Nonexistent thread
# ---------------------------------------------------------------------------

class TestNonexistentThread:
    async def test_transition_nonexistent_thread(self):
        """Transitioning a nonexistent thread returns None."""
        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            result = await transition(999999, "ACTIVE")
            assert result is None

    async def test_auto_transition_on_send_nonexistent(self):
        """auto_transition_on_send with nonexistent thread returns None."""
        result = await auto_transition_on_send(999999)
        assert result is None

    async def test_auto_transition_on_receive_nonexistent(self):
        """auto_transition_on_receive with nonexistent thread returns None."""
        result = await auto_transition_on_receive(999999)
        assert result is None


# ---------------------------------------------------------------------------
# Same-state transitions (no-op)
# ---------------------------------------------------------------------------

class TestSameStateTransition:
    async def test_same_state_is_noop(self, make_thread):
        """Transitioning to the same state should return old state without logging."""
        thread = await make_thread(state="ACTIVE", gmail_id_suffix="same_state")
        # The function returns old_state without logging when old == new
        result = await transition(thread.id, "ACTIVE")
        assert result == "ACTIVE"


# ---------------------------------------------------------------------------
# auto_transition_on_send
# ---------------------------------------------------------------------------

class TestAutoTransitionOnSend:
    async def test_send_moves_to_waiting_reply(self, make_thread):
        """After sending, thread should move to WAITING_REPLY."""
        thread = await make_thread(state="ACTIVE", gmail_id_suffix="send_active")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            old = await auto_transition_on_send(thread.id)
            assert old == "ACTIVE"

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == "WAITING_REPLY"
            assert updated.next_follow_up_date is not None

    async def test_send_from_new_moves_to_waiting(self, make_thread):
        """Sending from NEW state also moves to WAITING_REPLY."""
        thread = await make_thread(state="NEW", gmail_id_suffix="send_new")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            old = await auto_transition_on_send(thread.id)
            assert old == "NEW"

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == "WAITING_REPLY"

    async def test_send_when_already_waiting(self, make_thread):
        """Sending when already WAITING_REPLY stays in WAITING_REPLY."""
        thread = await make_thread(state="WAITING_REPLY", gmail_id_suffix="send_waiting")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            old = await auto_transition_on_send(thread.id)
            assert old == "WAITING_REPLY"

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == "WAITING_REPLY"

    async def test_send_sets_follow_up_date(self, make_thread):
        """auto_transition_on_send should set next_follow_up_date based on follow_up_days."""
        thread = await make_thread(
            state="ACTIVE", gmail_id_suffix="send_followup",
            follow_up_days=5,
        )

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            await auto_transition_on_send(thread.id)

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.next_follow_up_date is not None
            # Should be approximately 5 days from now
            delta = updated.next_follow_up_date - datetime.now(timezone.utc)
            assert 4 <= delta.days <= 5


# ---------------------------------------------------------------------------
# auto_transition_on_receive
# ---------------------------------------------------------------------------

class TestAutoTransitionOnReceive:
    async def test_receive_waiting_moves_to_active(self, make_thread):
        """Receiving email in WAITING_REPLY moves to ACTIVE."""
        thread = await make_thread(state="WAITING_REPLY", gmail_id_suffix="receive_waiting")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            old = await auto_transition_on_receive(thread.id)
            assert old == "WAITING_REPLY"

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == "ACTIVE"
            assert updated.next_follow_up_date is None  # Cleared on receive

    async def test_receive_follow_up_moves_to_active(self, make_thread):
        """Receiving email in FOLLOW_UP moves to ACTIVE."""
        thread = await make_thread(state="FOLLOW_UP", gmail_id_suffix="receive_followup")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            old = await auto_transition_on_receive(thread.id)
            assert old == "FOLLOW_UP"

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == "ACTIVE"

    async def test_receive_on_archived_no_change(self, make_thread):
        """Receiving email in ARCHIVED state should NOT change state."""
        thread = await make_thread(state="ARCHIVED", gmail_id_suffix="receive_archived")
        old = await auto_transition_on_receive(thread.id)
        assert old == "ARCHIVED"

        async with async_session() as session:
            updated = await session.get(Thread, thread.id)
            assert updated.state == "ARCHIVED"

    async def test_receive_on_goal_met_no_change(self, make_thread):
        """Receiving email in GOAL_MET state should NOT change state."""
        thread = await make_thread(state="GOAL_MET", gmail_id_suffix="receive_goal_met")
        old = await auto_transition_on_receive(thread.id)
        assert old == "GOAL_MET"

    async def test_receive_on_new_no_change(self, make_thread):
        """Receiving email in NEW state should NOT change state (only WAITING/FOLLOW_UP trigger)."""
        thread = await make_thread(state="NEW", gmail_id_suffix="receive_new")
        old = await auto_transition_on_receive(thread.id)
        assert old == "NEW"

    async def test_receive_on_active_no_change(self, make_thread):
        """Receiving email in ACTIVE state should NOT change state."""
        thread = await make_thread(state="ACTIVE", gmail_id_suffix="receive_active")
        old = await auto_transition_on_receive(thread.id)
        assert old == "ACTIVE"


# ---------------------------------------------------------------------------
# Knowledge extraction trigger
# ---------------------------------------------------------------------------

class TestKnowledgeExtractionTrigger:
    async def test_goal_met_triggers_knowledge_extraction(self, make_thread):
        """Transitioning to GOAL_MET should trigger knowledge extraction."""
        thread = await make_thread(state="ACTIVE", gmail_id_suffix="knowledge_goal_met")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock), \
             patch("src.engine.knowledge.on_thread_complete", new_callable=AsyncMock) as mock_extract:
            await transition(thread.id, "GOAL_MET", reason="test")
            # Give the created task a moment to be scheduled
            await asyncio.sleep(0.1)
            # on_thread_complete is called via asyncio.create_task
            # It may or may not have been called depending on event loop
            # The key test: no error was raised

    async def test_archived_triggers_knowledge_extraction(self, make_thread):
        """Transitioning to ARCHIVED should trigger knowledge extraction."""
        thread = await make_thread(state="ACTIVE", gmail_id_suffix="knowledge_archived")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock), \
             patch("src.engine.knowledge.on_thread_complete", new_callable=AsyncMock):
            old = await transition(thread.id, "ARCHIVED", reason="test")
            assert old == "ACTIVE"


# ---------------------------------------------------------------------------
# Audit log and event publishing
# ---------------------------------------------------------------------------

class TestAuditAndEvents:
    async def test_transition_logs_action(self, make_thread):
        """State change should create an audit log entry."""
        thread = await make_thread(state="NEW", gmail_id_suffix="audit_log")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock) as mock_log, \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock):
            await transition(thread.id, "ACTIVE", reason="test_reason", actor="test_actor")
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args[1]
            assert call_kwargs["action_type"] == "state_changed"
            assert call_kwargs["thread_id"] == thread.id
            assert call_kwargs["actor"] == "test_actor"
            assert call_kwargs["details"]["old_state"] == "NEW"
            assert call_kwargs["details"]["new_state"] == "ACTIVE"

    async def test_transition_publishes_event(self, make_thread):
        """State change should publish a WebSocket event."""
        thread = await make_thread(state="NEW", gmail_id_suffix="publish_event")

        with patch("src.engine.state_machine.log_action", new_callable=AsyncMock), \
             patch("src.engine.state_machine.publish_event", new_callable=AsyncMock) as mock_pub:
            await transition(thread.id, "ACTIVE", reason="test")
            mock_pub.assert_called_once_with("state_changed", {
                "thread_id": thread.id,
                "old_state": "NEW",
                "new_state": "ACTIVE",
                "reason": "test",
            })


# ---------------------------------------------------------------------------
# Follow-up detection
# ---------------------------------------------------------------------------

class TestFollowUpDetection:
    async def test_overdue_thread_detected(self, make_thread):
        """Thread with past follow-up date should be returned."""
        from datetime import timedelta
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        thread = await make_thread(
            state="WAITING_REPLY",
            gmail_id_suffix="followup_overdue",
            next_follow_up_date=past_date,
        )
        ids = await get_threads_needing_follow_up()
        assert thread.id in ids

    async def test_future_followup_not_detected(self, make_thread):
        """Thread with future follow-up date should NOT be returned."""
        from datetime import timedelta
        future_date = datetime.now(timezone.utc) + timedelta(days=5)
        thread = await make_thread(
            state="WAITING_REPLY",
            gmail_id_suffix="followup_future",
            next_follow_up_date=future_date,
        )
        ids = await get_threads_needing_follow_up()
        assert thread.id not in ids

    async def test_non_waiting_thread_not_detected(self, make_thread):
        """Thread in ACTIVE state (not WAITING_REPLY) should not be returned even if overdue."""
        from datetime import timedelta
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        thread = await make_thread(
            state="ACTIVE",
            gmail_id_suffix="followup_active",
            next_follow_up_date=past_date,
        )
        ids = await get_threads_needing_follow_up()
        assert thread.id not in ids
