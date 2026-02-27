"""Tests for src/engine/followup.py — follow-up management."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSetFollowUp:
    @pytest.mark.asyncio
    async def test_returns_false_when_thread_not_found(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.followup.async_session", return_value=mock_session):
            from src.engine.followup import set_follow_up
            result = await set_follow_up(999, 7)

        assert result is False

    @pytest.mark.asyncio
    async def test_sets_follow_up_days_and_returns_true(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.followup.async_session", return_value=mock_session):
            with patch("src.engine.followup.log_action", new_callable=AsyncMock):
                from src.engine.followup import set_follow_up
                result = await set_follow_up(1, 5)

        assert result is True
        assert mock_thread.follow_up_days == 5

    @pytest.mark.asyncio
    async def test_logs_follow_up_set_action(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.followup.async_session", return_value=mock_session):
            with patch("src.engine.followup.log_action", new_callable=AsyncMock) as mock_log:
                from src.engine.followup import set_follow_up
                await set_follow_up(3, 10, actor="user")

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["action_type"] == "follow_up_set"
        assert call_kwargs["thread_id"] == 3
        assert call_kwargs["actor"] == "user"
        assert call_kwargs["details"] == {"days": 10}


class TestCheckFollowUps:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_threads_overdue(self) -> None:
        with patch("src.engine.followup.get_threads_needing_follow_up",
                   new_callable=AsyncMock, return_value=[]):
            from src.engine.followup import check_follow_ups
            result = await check_follow_ups()

        assert result == []

    @pytest.mark.asyncio
    async def test_triggers_follow_up_for_each_overdue_thread(self) -> None:
        with patch("src.engine.followup.get_threads_needing_follow_up",
                   new_callable=AsyncMock, return_value=[1, 2, 3]):
            with patch("src.engine.followup.trigger_follow_up",
                       new_callable=AsyncMock) as mock_trigger:
                from src.engine.followup import check_follow_ups
                result = await check_follow_ups()

        assert result == [1, 2, 3]
        assert mock_trigger.call_count == 3
        mock_trigger.assert_any_call(1)
        mock_trigger.assert_any_call(2)
        mock_trigger.assert_any_call(3)

    @pytest.mark.asyncio
    async def test_returns_list_of_triggered_thread_ids(self) -> None:
        with patch("src.engine.followup.get_threads_needing_follow_up",
                   new_callable=AsyncMock, return_value=[5, 8]):
            with patch("src.engine.followup.trigger_follow_up", new_callable=AsyncMock):
                from src.engine.followup import check_follow_ups
                result = await check_follow_ups()

        assert result == [5, 8]


class TestTriggerFollowUp:
    @pytest.mark.asyncio
    async def test_transitions_thread_to_follow_up_state(self) -> None:
        with patch("src.engine.followup.transition", new_callable=AsyncMock) as mock_transition:
            with patch("src.engine.followup.publish_event", new_callable=AsyncMock):
                with patch("src.engine.followup.log_action", new_callable=AsyncMock):
                    from src.engine.followup import trigger_follow_up
                    await trigger_follow_up(7)

        mock_transition.assert_called_once_with(
            7, "FOLLOW_UP", reason="follow_up_overdue", actor="system"
        )

    @pytest.mark.asyncio
    async def test_publishes_follow_up_triggered_event(self) -> None:
        with patch("src.engine.followup.transition", new_callable=AsyncMock):
            with patch("src.engine.followup.publish_event", new_callable=AsyncMock) as mock_publish:
                with patch("src.engine.followup.log_action", new_callable=AsyncMock):
                    from src.engine.followup import trigger_follow_up
                    await trigger_follow_up(7)

        mock_publish.assert_called_once_with("follow_up_triggered", {"thread_id": 7})

    @pytest.mark.asyncio
    async def test_logs_follow_up_triggered_action(self) -> None:
        with patch("src.engine.followup.transition", new_callable=AsyncMock):
            with patch("src.engine.followup.publish_event", new_callable=AsyncMock):
                with patch("src.engine.followup.log_action", new_callable=AsyncMock) as mock_log:
                    from src.engine.followup import trigger_follow_up
                    await trigger_follow_up(4)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["action_type"] == "follow_up_triggered"
        assert call_kwargs["thread_id"] == 4
        assert call_kwargs["actor"] == "system"
