"""Tests for src/engine/goals.py — goal management for threads."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSetGoal:
    @pytest.mark.asyncio
    async def test_returns_false_when_thread_not_found(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            from src.engine.goals import set_goal
            result = await set_goal(999, "close deal")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_and_sets_goal_on_thread(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                    from src.engine.goals import set_goal
                    result = await set_goal(1, "close the deal", "They confirm in writing")

        assert result is True
        assert mock_thread.goal == "close the deal"
        assert mock_thread.acceptance_criteria == "They confirm in writing"
        assert mock_thread.goal_status == "in_progress"

    @pytest.mark.asyncio
    async def test_publishes_goal_updated_event(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock) as mock_publish:
                    from src.engine.goals import set_goal
                    await set_goal(1, "my goal")

        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "goal_updated"
        assert call_args[0][1]["thread_id"] == 1
        assert call_args[0][1]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_logs_goal_set_action(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock) as mock_log:
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                    from src.engine.goals import set_goal
                    await set_goal(5, "win contract", actor="user")

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["action_type"] == "goal_set"
        assert call_kwargs["thread_id"] == 5
        assert call_kwargs["actor"] == "user"

    @pytest.mark.asyncio
    async def test_acceptance_criteria_defaults_to_none(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                    from src.engine.goals import set_goal
                    await set_goal(1, "close deal")

        assert mock_thread.acceptance_criteria is None


class TestUpdateGoalStatus:
    @pytest.mark.asyncio
    async def test_raises_value_error_for_invalid_status(self) -> None:
        from src.engine.goals import update_goal_status
        with pytest.raises(ValueError, match="Invalid goal status"):
            await update_goal_status(1, "invalid_status")

    @pytest.mark.asyncio
    async def test_returns_false_when_thread_not_found(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            from src.engine.goals import update_goal_status
            result = await update_goal_status(999, "met")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_thread_has_no_goal(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = None
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            from src.engine.goals import update_goal_status
            result = await update_goal_status(1, "met")

        assert result is False

    @pytest.mark.asyncio
    async def test_updates_status_and_returns_true(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = "close deal"
        mock_thread.goal_status = "in_progress"
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                    from src.engine.goals import update_goal_status
                    result = await update_goal_status(1, "abandoned")

        assert result is True
        assert mock_thread.goal_status == "abandoned"

    @pytest.mark.asyncio
    async def test_triggers_state_machine_transition_when_met(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = "close deal"
        mock_thread.goal_status = "in_progress"
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                    with patch("src.engine.state_machine.transition", new_callable=AsyncMock) as mock_transition:
                        from src.engine.goals import update_goal_status
                        await update_goal_status(1, "met")

        mock_transition.assert_called_once_with(1, "GOAL_MET", reason="goal_met", actor="system")

    @pytest.mark.asyncio
    async def test_no_state_transition_when_status_is_abandoned(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = "close deal"
        mock_thread.goal_status = "in_progress"
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                    with patch("src.engine.state_machine.transition", new_callable=AsyncMock) as mock_transition:
                        from src.engine.goals import update_goal_status
                        await update_goal_status(1, "abandoned")

        mock_transition.assert_not_called()

    @pytest.mark.asyncio
    async def test_accepts_all_valid_statuses(self) -> None:
        from src.engine.goals import update_goal_status
        for status in ("in_progress", "met", "abandoned"):
            mock_thread = MagicMock()
            mock_thread.goal = "a goal"
            mock_thread.goal_status = "in_progress"
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)

            with patch("src.engine.goals.async_session", return_value=mock_session):
                with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                    with patch("src.engine.goals.publish_event", new_callable=AsyncMock):
                        with patch("src.engine.state_machine.transition", new_callable=AsyncMock):
                            result = await update_goal_status(1, status)
            assert result is True


class TestClearGoal:
    @pytest.mark.asyncio
    async def test_returns_false_when_thread_not_found(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            from src.engine.goals import clear_goal
            result = await clear_goal(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_clears_goal_fields_and_returns_true(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock):
                from src.engine.goals import clear_goal
                result = await clear_goal(1)

        assert result is True
        assert mock_thread.goal is None
        assert mock_thread.acceptance_criteria is None
        assert mock_thread.goal_status is None

    @pytest.mark.asyncio
    async def test_logs_goal_cleared_action(self) -> None:
        mock_thread = MagicMock()
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.async_session", return_value=mock_session):
            with patch("src.engine.goals.log_action", new_callable=AsyncMock) as mock_log:
                from src.engine.goals import clear_goal
                await clear_goal(3, actor="user")

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["action_type"] == "goal_cleared"
        assert call_kwargs["thread_id"] == 3
        assert call_kwargs["actor"] == "user"


class TestCheckGoalMet:
    @pytest.mark.asyncio
    async def test_returns_not_met_when_llm_unavailable(self) -> None:
        with patch("src.engine.goals.llm_available", return_value=False):
            from src.engine.goals import check_goal_met
            result = await check_goal_met(1)

        assert result["met"] is False
        assert "LLM not available" in result["reason"]

    @pytest.mark.asyncio
    async def test_returns_not_met_when_thread_not_found(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.llm_available", return_value=True):
            with patch("src.engine.goals.async_session", return_value=mock_session):
                from src.engine.goals import check_goal_met
                result = await check_goal_met(999)

        assert result["met"] is False
        assert "No goal set" in result["reason"]

    @pytest.mark.asyncio
    async def test_returns_not_met_when_thread_has_no_goal(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = None
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.llm_available", return_value=True):
            with patch("src.engine.goals.async_session", return_value=mock_session):
                from src.engine.goals import check_goal_met
                result = await check_goal_met(1)

        assert result["met"] is False

    @pytest.mark.asyncio
    async def test_calls_llm_and_returns_result(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = "close the deal"
        mock_thread.acceptance_criteria = "Written confirmation received"
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.llm_available", return_value=True):
            with patch("src.engine.goals.async_session", return_value=mock_session):
                with patch("src.engine.goals.complete_json", new_callable=AsyncMock,
                           return_value={"met": False, "reason": "No response yet"}):
                    from src.engine.goals import check_goal_met
                    result = await check_goal_met(1)

        assert result["met"] is False
        assert result["reason"] == "No response yet"

    @pytest.mark.asyncio
    async def test_updates_status_to_met_when_llm_says_met(self) -> None:
        mock_thread = MagicMock()
        mock_thread.goal = "close the deal"
        mock_thread.acceptance_criteria = None
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.goals.llm_available", return_value=True):
            with patch("src.engine.goals.async_session", return_value=mock_session):
                with patch("src.engine.goals.complete_json", new_callable=AsyncMock,
                           return_value={"met": True, "reason": "Confirmation email received"}):
                    with patch("src.engine.goals.update_goal_status", new_callable=AsyncMock) as mock_update:
                        from src.engine.goals import check_goal_met
                        result = await check_goal_met(1)

        assert result["met"] is True
        mock_update.assert_called_once_with(1, "met", actor="system")
