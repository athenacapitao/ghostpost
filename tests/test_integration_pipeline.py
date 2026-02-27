"""Integration tests for GhostPost data pipelines and engine modules.

Tests the state machine, notification filtering, and settings I/O using the
real database — not mocks. These complement the unit tests by catching wiring
bugs that only appear when the full stack is assembled.
"""

import pytest
import pytest_asyncio

from src.engine.state_machine import (
    STATES,
    auto_transition_on_receive,
    auto_transition_on_send,
    get_threads_needing_follow_up,
    transition,
)
from src.engine.notifications import should_notify, EVENT_SETTING_MAP
from src.db.models import Thread, Setting
from src.db.session import async_session

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_thread(**kwargs) -> Thread:
    defaults = dict(gmail_thread_id=None, subject="Pipeline Test", state="NEW")
    defaults.update(kwargs)
    async with async_session() as session:
        thread = Thread(**defaults)
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
    return thread


async def _delete_thread(thread_id: int) -> None:
    async with async_session() as session:
        obj = await session.get(Thread, thread_id)
        if obj:
            await session.delete(obj)
            await session.commit()


# ---------------------------------------------------------------------------
# State machine — valid states registry
# ---------------------------------------------------------------------------

class TestStateMachineStates:
    async def test_all_expected_states_are_registered(self):
        """The STATES set must contain every valid lifecycle state."""
        expected = {"NEW", "ACTIVE", "WAITING_REPLY", "FOLLOW_UP", "GOAL_MET", "ARCHIVED"}
        assert expected == STATES

    async def test_invalid_state_raises_value_error(self):
        """transition() must raise ValueError immediately for unknown states."""
        with pytest.raises(ValueError, match="Invalid state"):
            await transition(1, "INVALID_STATE")

    async def test_nonexistent_thread_returns_none(self):
        """transition() must return None (not raise) when the thread does not exist."""
        result = await transition(999999999, "ACTIVE")
        assert result is None


# ---------------------------------------------------------------------------
# State machine — real DB transitions
# ---------------------------------------------------------------------------

class TestStateMachineTransitions:
    @pytest_asyncio.fixture(autouse=True)
    async def setup_thread(self):
        """Create an isolated thread for each test; delete it afterwards."""
        self.thread = await _create_thread(
            gmail_thread_id="pipe_test_sm_001",
            state="NEW",
        )
        yield
        await _delete_thread(self.thread.id)

    async def test_transition_changes_state_in_db(self):
        """Calling transition() must persist the new state to the database."""
        old = await transition(self.thread.id, "ACTIVE", reason="test")
        assert old == "NEW"

        async with async_session() as session:
            updated = await session.get(Thread, self.thread.id)
        assert updated.state == "ACTIVE"

    async def test_transition_same_state_is_no_op(self):
        """Transitioning to the current state must return that state without error."""
        await transition(self.thread.id, "ACTIVE")
        result = await transition(self.thread.id, "ACTIVE")
        # Returns old_state == current_state for no-op
        assert result == "ACTIVE"

    async def test_auto_transition_on_send_sets_waiting_reply(self):
        """Sending a reply must move the thread to WAITING_REPLY."""
        await transition(self.thread.id, "ACTIVE")
        old = await auto_transition_on_send(self.thread.id)
        assert old == "ACTIVE"

        async with async_session() as session:
            updated = await session.get(Thread, self.thread.id)
        assert updated.state == "WAITING_REPLY"

    async def test_auto_transition_on_send_sets_follow_up_date(self):
        """auto_transition_on_send must populate next_follow_up_date."""
        await transition(self.thread.id, "ACTIVE")
        await auto_transition_on_send(self.thread.id)

        async with async_session() as session:
            updated = await session.get(Thread, self.thread.id)
        assert updated.next_follow_up_date is not None

    async def test_auto_transition_on_receive_from_waiting_reply(self):
        """Receiving an email while WAITING_REPLY must move thread to ACTIVE."""
        await transition(self.thread.id, "WAITING_REPLY")
        old = await auto_transition_on_receive(self.thread.id)
        assert old == "WAITING_REPLY"

        async with async_session() as session:
            updated = await session.get(Thread, self.thread.id)
        assert updated.state == "ACTIVE"

    async def test_auto_transition_on_receive_clears_follow_up_date(self):
        """Receiving a reply must clear the next_follow_up_date."""
        await transition(self.thread.id, "WAITING_REPLY")
        await auto_transition_on_receive(self.thread.id)

        async with async_session() as session:
            updated = await session.get(Thread, self.thread.id)
        assert updated.next_follow_up_date is None

    async def test_auto_transition_on_receive_ignores_active_threads(self):
        """auto_transition_on_receive must not change state if thread is already ACTIVE."""
        await transition(self.thread.id, "ACTIVE")
        result = await auto_transition_on_receive(self.thread.id)
        # Returns current state without transitioning
        assert result == "ACTIVE"

        async with async_session() as session:
            updated = await session.get(Thread, self.thread.id)
        assert updated.state == "ACTIVE"

    async def test_auto_transition_on_send_returns_none_for_missing_thread(self):
        result = await auto_transition_on_send(999999999)
        assert result is None

    async def test_auto_transition_on_receive_returns_none_for_missing_thread(self):
        result = await auto_transition_on_receive(999999999)
        assert result is None


# ---------------------------------------------------------------------------
# State machine — follow-up scheduling query
# ---------------------------------------------------------------------------

class TestGetThreadsNeedingFollowUp:
    async def test_returns_list(self):
        """get_threads_needing_follow_up() must always return a list."""
        result = await get_threads_needing_follow_up()
        assert isinstance(result, list)

    async def test_overdue_thread_appears_in_results(self):
        """A WAITING_REPLY thread with a past follow-up date must be returned."""
        from datetime import datetime, timedelta, timezone

        thread = await _create_thread(
            gmail_thread_id="pipe_test_followup_overdue",
            state="WAITING_REPLY",
        )
        try:
            # Set follow-up date in the past
            async with async_session() as session:
                obj = await session.get(Thread, thread.id)
                obj.next_follow_up_date = datetime.now(timezone.utc) - timedelta(days=1)
                await session.commit()

            result = await get_threads_needing_follow_up()
            assert thread.id in result
        finally:
            await _delete_thread(thread.id)

    async def test_future_follow_up_not_in_results(self):
        """A thread with a future follow-up date must NOT appear yet."""
        from datetime import datetime, timedelta, timezone

        thread = await _create_thread(
            gmail_thread_id="pipe_test_followup_future",
            state="WAITING_REPLY",
        )
        try:
            async with async_session() as session:
                obj = await session.get(Thread, thread.id)
                obj.next_follow_up_date = datetime.now(timezone.utc) + timedelta(days=7)
                await session.commit()

            result = await get_threads_needing_follow_up()
            assert thread.id not in result
        finally:
            await _delete_thread(thread.id)


# ---------------------------------------------------------------------------
# Notification filtering — uses real DB for setting lookups
# ---------------------------------------------------------------------------

class TestNotificationFiltering:
    async def test_should_notify_returns_true_for_known_event_with_default_settings(self):
        """Known event types default to True when no override is stored in the DB."""
        # goal_met maps to notification_goal_met which defaults to "true"
        result = await should_notify("goal_met")
        assert result is True

    async def test_should_notify_returns_true_for_draft_ready_by_default(self):
        result = await should_notify("draft_ready")
        assert result is True

    async def test_should_notify_returns_false_for_unknown_event_type(self):
        """should_notify() must return False for event types not in the mapping."""
        result = await should_notify("totally_made_up_event_xyz")
        assert result is False

    async def test_all_mapped_event_types_return_true_by_default(self):
        """Every event in EVENT_SETTING_MAP must default to enabled."""
        for event_type in EVENT_SETTING_MAP:
            result = await should_notify(event_type)
            assert result is True, f"Expected True for event_type={event_type!r}"

    async def test_should_notify_respects_db_setting_disabled(self):
        """When a notification setting is set to 'false' in the DB, should_notify returns False."""
        setting_key = "notification_goal_met"
        async with async_session() as session:
            existing = await session.get(Setting, setting_key)
            if existing:
                original_value = existing.value
                existing.value = "false"
            else:
                original_value = None
                session.add(Setting(key=setting_key, value="false"))
            await session.commit()

        try:
            result = await should_notify("goal_met")
            assert result is False
        finally:
            # Restore
            async with async_session() as session:
                setting = await session.get(Setting, setting_key)
                if original_value is None:
                    await session.delete(setting)
                else:
                    setting.value = original_value
                await session.commit()

    async def test_should_notify_respects_db_setting_enabled(self):
        """When a notification setting is explicitly 'true' in the DB, should_notify returns True."""
        setting_key = "notification_stale_thread"
        async with async_session() as session:
            existing = await session.get(Setting, setting_key)
            if existing:
                original_value = existing.value
                existing.value = "true"
            else:
                original_value = None
                session.add(Setting(key=setting_key, value="true"))
            await session.commit()

        try:
            result = await should_notify("stale_thread")
            assert result is True
        finally:
            async with async_session() as session:
                setting = await session.get(Setting, setting_key)
                if original_value is None:
                    await session.delete(setting)
                else:
                    setting.value = original_value
                await session.commit()
