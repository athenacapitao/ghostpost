"""Tests for src/engine/notifications.py — notification filtering engine."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_session(setting_value: str | None = None):
    """Return a mock async_session context manager.

    If setting_value is None, session.get returns None (simulates missing row).
    Otherwise it returns a MagicMock with .value set to setting_value.
    """
    if setting_value is None:
        mock_setting = None
    else:
        mock_setting = MagicMock()
        mock_setting.value = setting_value

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_setting)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ---------------------------------------------------------------------------
# _get_notification_setting
# ---------------------------------------------------------------------------

class TestGetNotificationSetting:
    @pytest.mark.asyncio
    async def test_returns_true_when_setting_is_true_string(self) -> None:
        mock_session = _make_mock_session("true")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import _get_notification_setting
            result = await _get_notification_setting("notification_new_email")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_setting_is_false_string(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import _get_notification_setting
            result = await _get_notification_setting("notification_new_email")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_numeric_one_string(self) -> None:
        mock_session = _make_mock_session("1")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import _get_notification_setting
            result = await _get_notification_setting("notification_new_email")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_yes_string(self) -> None:
        mock_session = _make_mock_session("yes")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import _get_notification_setting
            result = await _get_notification_setting("notification_new_email")
        assert result is True

    @pytest.mark.asyncio
    async def test_falls_back_to_default_when_no_db_row(self) -> None:
        # No setting in DB — default for notification_new_email is "true"
        mock_session = _make_mock_session(None)
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import _get_notification_setting
            result = await _get_notification_setting("notification_new_email")
        assert result is True

    @pytest.mark.asyncio
    async def test_falls_back_to_true_for_unknown_key_with_no_db_row(self) -> None:
        mock_session = _make_mock_session(None)
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import _get_notification_setting
            result = await _get_notification_setting("notification_nonexistent_key")
        assert result is True


# ---------------------------------------------------------------------------
# should_notify
# ---------------------------------------------------------------------------

class TestShouldNotify:
    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_event_type(self) -> None:
        from src.engine.notifications import should_notify
        result = await should_notify("totally_unknown_event")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_setting_is_enabled(self) -> None:
        mock_session = _make_mock_session("true")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import should_notify
            result = await should_notify("new_high_urgency_email")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_setting_is_disabled(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import should_notify
            result = await should_notify("new_high_urgency_email")
        assert result is False

    @pytest.mark.asyncio
    async def test_security_events_share_security_alert_setting(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import should_notify
            for event in ("injection_detected", "anomaly_detected", "email_quarantined",
                          "commitment_detected", "security_alert"):
                result = await should_notify(event)
                assert result is False, f"Expected False for event {event}"

    @pytest.mark.asyncio
    async def test_each_known_event_type_resolves_without_error(self) -> None:
        mock_session = _make_mock_session("true")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import should_notify, EVENT_SETTING_MAP
            for event_type in EVENT_SETTING_MAP:
                result = await should_notify(event_type)
                assert result is True


# ---------------------------------------------------------------------------
# dispatch_notification
# ---------------------------------------------------------------------------

class TestDispatchNotification:
    @pytest.mark.asyncio
    async def test_returns_false_when_setting_disabled(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import dispatch_notification
            result = await dispatch_notification(
                event_type="new_high_urgency_email",
                title="Test",
                message="Test message",
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_event_type(self) -> None:
        from src.engine.notifications import dispatch_notification
        result = await dispatch_notification(
            event_type="unknown_event",
            title="Test",
            message="Test message",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_notification_dispatched(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import dispatch_notification
                        result = await dispatch_notification(
                            event_type="goal_met",
                            title="Goal achieved",
                            message="The deal was closed.",
                            thread_id=1,
                            severity="info",
                        )
        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.allow_alerts_file_write
    async def test_writes_alert_to_file_on_dispatch(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import dispatch_notification
                        await dispatch_notification(
                            event_type="goal_met",
                            title="Deal closed",
                            message="Written confirmation received.",
                            thread_id=5,
                        )
            assert os.path.isfile(alerts_path)
            with open(alerts_path) as f:
                content = f.read()
            assert "Deal closed" in content
            assert "thread #5" in content

    @pytest.mark.asyncio
    async def test_publishes_redis_event_on_dispatch(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event",
                               new_callable=AsyncMock) as mock_publish:
                        from src.engine.notifications import dispatch_notification
                        await dispatch_notification(
                            event_type="draft_ready",
                            title="Draft ready",
                            message="Draft #3 awaiting approval.",
                            thread_id=2,
                        )
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == "notification"
        assert call_args[0][1]["event_type"] == "draft_ready"

    @pytest.mark.asyncio
    async def test_dispatch_does_not_raise_when_redis_fails(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event",
                               new_callable=AsyncMock, side_effect=RuntimeError("redis down")):
                        from src.engine.notifications import dispatch_notification
                        # Must not raise even when Redis is unavailable
                        result = await dispatch_notification(
                            event_type="goal_met",
                            title="Test",
                            message="Test message.",
                        )
        assert result is True


# ---------------------------------------------------------------------------
# _append_alert
# ---------------------------------------------------------------------------

class TestAppendAlert:
    # These tests call _append_alert directly with ALERTS_FILE redirected to a
    # temp directory, so they are safe to run without the global alert guard.
    pytestmark = [pytest.mark.allow_alerts_file_write]

    def test_creates_alerts_file_with_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert({
                    "timestamp": "2026-02-24T10:00:00+00:00",
                    "severity": "info",
                    "title": "Test alert",
                    "message": "Something happened.",
                    "thread_id": None,
                })
            with open(alerts_path) as f:
                content = f.read()
        assert content.startswith("# Active Alerts")
        assert "Test alert" in content

    def test_includes_thread_id_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert({
                    "timestamp": "2026-02-24T10:00:00+00:00",
                    "severity": "high",
                    "title": "Injection detected",
                    "message": "Prompt injection attempt in email body.",
                    "thread_id": 42,
                })
            with open(alerts_path) as f:
                content = f.read()
        assert "thread #42" in content

    def test_keeps_at_most_50_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                # Write 60 entries
                for i in range(60):
                    _append_alert({
                        "timestamp": f"2026-02-24T10:00:{i:02d}+00:00",
                        "severity": "info",
                        "title": f"Alert {i}",
                        "message": f"Message {i}.",
                        "thread_id": None,
                    })
            with open(alerts_path) as f:
                content = f.read()
        # Count "- **[" markers which prefix each alert entry
        entry_count = content.count("- **[")
        assert entry_count <= 50

    def test_new_entry_appears_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert({
                    "timestamp": "2026-02-24T10:00:00+00:00",
                    "severity": "info",
                    "title": "First alert",
                    "message": "First.",
                    "thread_id": None,
                })
                _append_alert({
                    "timestamp": "2026-02-24T11:00:00+00:00",
                    "severity": "high",
                    "title": "Second alert",
                    "message": "Second.",
                    "thread_id": None,
                })
            with open(alerts_path) as f:
                content = f.read()
        # Second (most recent) entry should appear before first entry in the file
        pos_second = content.index("Second alert")
        pos_first = content.index("First alert")
        assert pos_second < pos_first

    def test_severity_label_appears_in_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert({
                    "timestamp": "2026-02-24T10:00:00+00:00",
                    "severity": "critical",
                    "title": "Critical event",
                    "message": "Very bad thing.",
                    "thread_id": None,
                })
            with open(alerts_path) as f:
                content = f.read()
        assert "CRITICAL" in content


# ---------------------------------------------------------------------------
# Convenience dispatchers
# ---------------------------------------------------------------------------

class TestNotifyNewEmail:
    @pytest.mark.asyncio
    async def test_returns_false_for_low_urgency(self) -> None:
        from src.engine.notifications import notify_new_email
        for urgency in ("low", "medium", "normal"):
            result = await notify_new_email(1, "Subject", "sender@example.com", urgency)
            assert result is False, f"Expected False for urgency={urgency}"

    @pytest.mark.asyncio
    async def test_dispatches_for_high_urgency(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_new_email
                        result = await notify_new_email(1, "Urgent matter", "boss@example.com", "high")
        assert result is True

    @pytest.mark.asyncio
    async def test_dispatches_for_critical_urgency(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_new_email
                        result = await notify_new_email(2, "CRITICAL", "cto@example.com", "critical")
        assert result is True


class TestNotifyGoalMet:
    @pytest.mark.asyncio
    async def test_dispatches_goal_met_notification(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_goal_met
                        result = await notify_goal_met(3, "Close deal", "sign contract")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_goal_met_setting_disabled(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import notify_goal_met
            result = await notify_goal_met(3, "Close deal", "sign contract")
        assert result is False


class TestNotifySecurityAlert:
    @pytest.mark.asyncio
    async def test_dispatches_security_alert(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_security_alert
                        result = await notify_security_alert(
                            thread_id=4,
                            event_type="injection_detected",
                            details="Pattern matched in subject line.",
                        )
        assert result is True

    @pytest.mark.asyncio
    async def test_accepts_none_thread_id(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_security_alert
                        result = await notify_security_alert(
                            thread_id=None,
                            event_type="anomaly_detected",
                            details="Unusual send rate.",
                            severity="critical",
                        )
        assert result is True


class TestNotifyDraftReady:
    @pytest.mark.asyncio
    async def test_dispatches_draft_ready_notification(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_draft_ready
                        result = await notify_draft_ready(7, "Re: Project update", 99)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_setting_disabled(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import notify_draft_ready
            result = await notify_draft_ready(7, "Re: Project update", 99)
        assert result is False


class TestNotifyStaleThread:
    # Tests redirect ALERTS_FILE to a temp directory, so the global guard is not needed.
    pytestmark = [pytest.mark.allow_alerts_file_write]

    @pytest.mark.asyncio
    async def test_dispatches_stale_thread_notification(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_stale_thread
                        result = await notify_stale_thread(10, "Partnership proposal", 5)
        assert result is True

    @pytest.mark.asyncio
    async def test_message_includes_days(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_stale_thread
                        await notify_stale_thread(10, "Partnership proposal", 7)
            with open(alerts_path) as f:
                content = f.read()
        assert "7 days" in content


class TestNotifyThreadComposed:
    # Tests redirect ALERTS_FILE to a temp directory, so the global guard is not needed.
    pytestmark = [pytest.mark.allow_alerts_file_write]

    @pytest.mark.asyncio
    async def test_dispatches_thread_composed_notification(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_thread_composed
                        result = await notify_thread_composed(11, "Partnership intro", "partner@example.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_message_includes_recipient_and_subject(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_thread_composed
                        await notify_thread_composed(11, "Partnership intro", "partner@example.com")
            with open(alerts_path) as f:
                content = f.read()
        assert "partner@example.com" in content
        assert "Partnership intro" in content

    @pytest.mark.asyncio
    async def test_message_includes_goal_when_provided(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_thread_composed
                        await notify_thread_composed(
                            12, "Sales outreach", "lead@example.com", goal="Close deal by Q2"
                        )
            with open(alerts_path) as f:
                content = f.read()
        assert "Close deal by Q2" in content

    @pytest.mark.asyncio
    async def test_message_omits_goal_line_when_goal_is_none(self) -> None:
        mock_session = _make_mock_session("true")
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.async_session", return_value=mock_session):
                with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                    with patch("src.engine.notifications.publish_event", new_callable=AsyncMock):
                        from src.engine.notifications import notify_thread_composed
                        await notify_thread_composed(13, "Quick hello", "friend@example.com", goal=None)
            with open(alerts_path) as f:
                content = f.read()
        assert "Goal:" not in content

    @pytest.mark.asyncio
    async def test_returns_false_when_setting_disabled(self) -> None:
        mock_session = _make_mock_session("false")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import notify_thread_composed
            result = await notify_thread_composed(14, "Test subject", "nobody@example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_event_type_maps_to_notification_new_email_setting(self) -> None:
        """thread_composed piggybacks on the notification_new_email setting."""
        mock_session = _make_mock_session("true")
        with patch("src.engine.notifications.async_session", return_value=mock_session):
            from src.engine.notifications import should_notify
            result = await should_notify("thread_composed")
        assert result is True


# ---------------------------------------------------------------------------
# Deduplication in _append_alert
# ---------------------------------------------------------------------------

class TestAppendAlertDeduplication:
    """Tests that _append_alert suppresses duplicate alerts."""

    pytestmark = [pytest.mark.allow_alerts_file_write]

    def _base_alert(self, thread_id: int | None = 7, message: str = "No reply received for 3 days. Follow-up recommended.") -> dict:
        return {
            "timestamp": "2026-02-25T09:00:00+00:00",
            "severity": "medium",
            "title": "Stale thread: Quarterly review",
            "message": message,
            "thread_id": thread_id,
        }

    def test_second_identical_alert_is_suppressed(self) -> None:
        """Writing the same (thread_id, message) twice should produce one entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert(self._base_alert())
                _append_alert(self._base_alert())
            with open(alerts_path) as f:
                content = f.read()
        assert content.count("Stale thread: Quarterly review") == 1

    def test_alert_with_different_message_is_not_suppressed(self) -> None:
        """Different message text must always produce a new entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert(self._base_alert(message="No reply received for 3 days. Follow-up recommended."))
                _append_alert(self._base_alert(message="No reply received for 4 days. Follow-up recommended."))
            with open(alerts_path) as f:
                content = f.read()
        assert content.count("Stale thread: Quarterly review") == 2

    def test_alert_with_different_thread_id_is_not_suppressed(self) -> None:
        """Same message but different thread_id must produce a new entry."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                _append_alert(self._base_alert(thread_id=7))
                _append_alert(self._base_alert(thread_id=8))
            with open(alerts_path) as f:
                content = f.read()
        assert content.count("Stale thread: Quarterly review") == 2

    def test_dedup_window_is_20_entries(self) -> None:
        """An alert that appeared more than 20 entries ago is NOT suppressed.

        The dedup window is the last 20 entries in the existing list.  After
        writing the target + 20 fillers, the target sits at position 21 from
        the front, which is index 20 from the end — one slot *past* the window.
        Writing 21 fillers guarantees the target is beyond position 20 from end.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert

                # Write the target alert first
                _append_alert(self._base_alert())

                # Flood 21 distinct entries to push the target outside the window
                for i in range(21):
                    _append_alert({
                        "timestamp": f"2026-02-25T09:{i:02d}:00+00:00",
                        "severity": "info",
                        "title": f"Filler alert {i}",
                        "message": f"Filler message {i}.",
                        "thread_id": 100 + i,
                    })

                # Re-write the original alert — it is now outside the 20-entry window
                _append_alert(self._base_alert())

            with open(alerts_path) as f:
                content = f.read()

        # The original alert must appear twice (first write + re-write after window)
        assert content.count("Stale thread: Quarterly review") == 2

    def test_none_thread_id_dedup_works(self) -> None:
        """Deduplication also functions when thread_id is None."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import _append_alert
                alert = self._base_alert(thread_id=None)
                _append_alert(alert)
                _append_alert(alert)
            with open(alerts_path) as f:
                content = f.read()
        assert content.count("Stale thread: Quarterly review") == 1


# ---------------------------------------------------------------------------
# cleanup_alerts
# ---------------------------------------------------------------------------

class TestCleanupAlerts:
    """Tests for the cleanup_alerts() maintenance function."""

    pytestmark = [pytest.mark.allow_alerts_file_write]

    def _write_alerts_file(self, path: str, entries: list[str]) -> None:
        """Write a minimal ALERTS.md with the given entry strings."""
        with open(path, "w") as f:
            f.write("# Active Alerts\n\n_Last updated: 2026-02-25 09:00 UTC_\n\n")
            for entry in entries:
                f.write(entry)

    def _make_entry(self, index: int, thread_id: int | None = None, message: str | None = None) -> str:
        msg = message or f"Message {index}."
        line1 = f"- **[2026-02-25 09:{index:02d}]** [INFO] Alert {index}"
        if thread_id is not None:
            line1 += f" (thread #{thread_id})"
        return f"{line1}\n  {msg}\n"

    def test_returns_zero_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import cleanup_alerts
                removed = cleanup_alerts()
        assert removed == 0

    def test_removes_duplicate_entries(self) -> None:
        """Duplicate entries (same thread_id + message) after the first are removed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            repeated_entry = self._make_entry(0, thread_id=5, message="No reply for 3 days. Follow-up recommended.")
            entries = [repeated_entry] * 5  # 5 identical entries
            self._write_alerts_file(alerts_path, entries)

            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import cleanup_alerts
                removed = cleanup_alerts()

            with open(alerts_path) as f:
                content = f.read()

        assert removed == 4  # 5 entries → 1 unique; 4 removed
        assert content.count("- **[") == 1

    def test_trims_to_50_entries(self) -> None:
        """More than 50 unique entries are trimmed to the last 50."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            entries = [self._make_entry(i) for i in range(60)]
            self._write_alerts_file(alerts_path, entries)

            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import cleanup_alerts
                removed = cleanup_alerts()

            with open(alerts_path) as f:
                content = f.read()

        assert removed == 10  # 60 unique → trim to 50; 10 removed
        assert content.count("- **[") == 50

    def test_preserves_file_when_no_cleanup_needed(self) -> None:
        """A file with unique entries under 50 is rewritten with no changes in count."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            entries = [self._make_entry(i) for i in range(10)]
            self._write_alerts_file(alerts_path, entries)

            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import cleanup_alerts
                removed = cleanup_alerts()

            with open(alerts_path) as f:
                content = f.read()

        assert removed == 0
        assert content.count("- **[") == 10

    def test_keeps_header_after_cleanup(self) -> None:
        """The ALERTS.md header is preserved after cleanup."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            alerts_path = os.path.join(tmp_dir, "ALERTS.md")
            entries = [self._make_entry(0)] * 3
            self._write_alerts_file(alerts_path, entries)

            with patch("src.engine.notifications.ALERTS_FILE", alerts_path):
                from src.engine.notifications import cleanup_alerts
                cleanup_alerts()

            with open(alerts_path) as f:
                content = f.read()

        assert content.startswith("# Active Alerts")
