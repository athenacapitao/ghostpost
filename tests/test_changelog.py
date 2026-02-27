"""Tests for _append_changelog and its call sites in notifications.py and sync.py."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _append_changelog unit tests
# ---------------------------------------------------------------------------


class TestAppendChangelog:
    """Tests for src.engine.context_writer._append_changelog."""

    def _invoke(self, tmp_dir: str, event_type: str, summary: str, severity: str = "INFO") -> str:
        """Call _append_changelog with CONTEXT_DIR redirected to tmp_dir and return file content."""
        import src.engine.context_writer as cw

        original_dir = cw.CONTEXT_DIR
        cw.CONTEXT_DIR = tmp_dir
        try:
            cw._append_changelog(event_type, summary, severity)
        finally:
            cw.CONTEXT_DIR = original_dir

        path = os.path.join(tmp_dir, "CHANGELOG.md")
        with open(path) as f:
            return f.read()

    def test_creates_file_with_header_on_first_call(self, tmp_path):
        content = self._invoke(str(tmp_path), "sync_complete", "5 new emails, 3 threads updated")

        assert "---" in content
        assert "schema_version: 1" in content
        assert "type: changelog" in content
        assert "# Changelog" in content

    def test_entry_format_is_correct(self, tmp_path):
        content = self._invoke(str(tmp_path), "sync_complete", "5 new emails, 3 threads updated")

        # Entry line should match "- [YYYY-MM-DD HH:MM] event_type: summary [SEVERITY]"
        import re
        pattern = r"- \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] sync_complete: 5 new emails, 3 threads updated \[INFO\]"
        assert re.search(pattern, content), f"Pattern not found in:\n{content}"

    def test_custom_severity_appears_in_entry(self, tmp_path):
        content = self._invoke(str(tmp_path), "security_alert", "injection on thread #7", "HIGH")
        assert "[HIGH]" in content

    def test_new_entries_prepended_before_old_ones(self, tmp_path):
        import src.engine.context_writer as cw

        original_dir = cw.CONTEXT_DIR
        cw.CONTEXT_DIR = str(tmp_path)
        try:
            cw._append_changelog("first_event", "first summary")
            cw._append_changelog("second_event", "second summary")
        finally:
            cw.CONTEXT_DIR = original_dir

        path = os.path.join(str(tmp_path), "CHANGELOG.md")
        with open(path) as f:
            content = f.read()

        first_pos = content.index("first_event")
        second_pos = content.index("second_event")
        # second_event was added last, so it should appear before first_event
        assert second_pos < first_pos, "Newest entry should appear before older entries"

    def test_trims_to_100_entries(self, tmp_path):
        import src.engine.context_writer as cw

        original_dir = cw.CONTEXT_DIR
        cw.CONTEXT_DIR = str(tmp_path)
        try:
            for i in range(110):
                cw._append_changelog("batch_event", f"entry {i}")
        finally:
            cw.CONTEXT_DIR = original_dir

        path = os.path.join(str(tmp_path), "CHANGELOG.md")
        with open(path) as f:
            content = f.read()

        entry_lines = [line for line in content.split("\n") if line.startswith("- [")]
        assert len(entry_lines) == 100, f"Expected 100 entries, got {len(entry_lines)}"

    def test_idempotent_header_on_multiple_calls(self, tmp_path):
        """Calling multiple times should not duplicate header/frontmatter lines."""
        import src.engine.context_writer as cw

        original_dir = cw.CONTEXT_DIR
        cw.CONTEXT_DIR = str(tmp_path)
        try:
            cw._append_changelog("event_a", "summary a")
            cw._append_changelog("event_b", "summary b")
        finally:
            cw.CONTEXT_DIR = original_dir

        path = os.path.join(str(tmp_path), "CHANGELOG.md")
        with open(path) as f:
            content = f.read()

        assert content.count("schema_version: 1") == 1
        assert content.count("# Changelog") == 1

    def test_write_is_atomic(self, tmp_path):
        """Verifies _atomic_write is used (temp file then rename) — no partial content."""
        import src.engine.context_writer as cw

        original_dir = cw.CONTEXT_DIR
        cw.CONTEXT_DIR = str(tmp_path)
        try:
            cw._append_changelog("test_event", "atomic test")
        finally:
            cw.CONTEXT_DIR = original_dir

        # No .tmp files should remain after the call
        tmp_files = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")]
        assert not tmp_files, f"Leftover temp files found: {tmp_files}"

    def test_file_not_required_to_exist_before_first_call(self, tmp_path):
        changelog_path = os.path.join(str(tmp_path), "CHANGELOG.md")
        assert not os.path.exists(changelog_path)

        import src.engine.context_writer as cw

        original_dir = cw.CONTEXT_DIR
        cw.CONTEXT_DIR = str(tmp_path)
        try:
            cw._append_changelog("init_event", "fresh start")
        finally:
            cw.CONTEXT_DIR = original_dir

        assert os.path.exists(changelog_path)

    def test_default_severity_is_info(self, tmp_path):
        content = self._invoke(str(tmp_path), "sync_complete", "no severity arg")
        assert "[INFO]" in content


# ---------------------------------------------------------------------------
# notifications.py integration — changelog calls
# ---------------------------------------------------------------------------


class TestNotificationsCallChangelog:
    """Verify that notification helper functions call _append_changelog."""

    @pytest.mark.asyncio
    async def test_notify_new_email_high_calls_changelog(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_new_email
            await notify_new_email(42, "Big Deal", "boss@corp.com", "high")

            mock_cl.assert_called_once_with(
                "new_email",
                'Thread #42 "Big Deal" from boss@corp.com',
                "HIGH",
            )

    @pytest.mark.asyncio
    async def test_notify_new_email_critical_calls_changelog_with_critical(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_new_email
            await notify_new_email(5, "Urgent", "cto@example.com", "critical")

            mock_cl.assert_called_once()
            args = mock_cl.call_args[0]
            assert args[2] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_notify_new_email_low_urgency_skips_changelog(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl:
            from src.engine.notifications import notify_new_email
            result = await notify_new_email(1, "Newsletter", "news@corp.com", "low")

            assert result is False
            mock_cl.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_goal_met_calls_changelog(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_goal_met
            await notify_goal_met(7, "Deal Thread", "Close the deal")

            mock_cl.assert_called_once_with("goal_met", "Thread #7 goal achieved", "INFO")

    @pytest.mark.asyncio
    async def test_notify_security_alert_calls_changelog(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_security_alert
            await notify_security_alert(3, "injection_detected", "found bad payload", "high")

            mock_cl.assert_called_once_with(
                "security_alert",
                "injection_detected on thread #3",
                "HIGH",
            )

    @pytest.mark.asyncio
    async def test_notify_security_alert_no_thread_id(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_security_alert
            await notify_security_alert(None, "anomaly_detected", "rate anomaly", "medium")

            mock_cl.assert_called_once()
            call_summary = mock_cl.call_args[0][1]
            assert "no thread" in call_summary

    @pytest.mark.asyncio
    async def test_notify_draft_ready_calls_changelog(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_draft_ready
            await notify_draft_ready(10, "Proposal", 55)

            mock_cl.assert_called_once_with(
                "draft_ready",
                "Draft #55 for thread #10 pending approval",
                "INFO",
            )

    @pytest.mark.asyncio
    async def test_notify_stale_thread_calls_changelog(self):
        with patch("src.engine.notifications._append_changelog") as mock_cl, \
             patch("src.engine.notifications.dispatch_notification", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True

            from src.engine.notifications import notify_stale_thread
            await notify_stale_thread(8, "Old Thread", 7)

            mock_cl.assert_called_once_with(
                "stale_thread",
                "Thread #8 no reply for 7d",
                "MEDIUM",
            )


# ---------------------------------------------------------------------------
# sync.py integration — changelog calls after publish_event
# ---------------------------------------------------------------------------


class TestSyncCallsChangelog:
    """Verify SyncEngine calls _append_changelog after successful syncs."""

    @pytest.mark.asyncio
    async def test_full_sync_calls_changelog(self):
        from src.gmail.sync import SyncEngine

        engine = SyncEngine()

        with patch.object(engine.client, "get_profile", new_callable=AsyncMock) as mock_profile, \
             patch.object(engine.client, "list_threads", new_callable=AsyncMock) as mock_list, \
             patch.object(engine.client, "get_thread", new_callable=AsyncMock) as mock_get_thread, \
             patch.object(engine, "_process_thread", new_callable=AsyncMock) as mock_process, \
             patch("src.gmail.sync.publish_event", new_callable=AsyncMock), \
             patch("src.gmail.sync._append_changelog") as mock_cl:

            mock_profile.return_value = {"historyId": "123"}
            mock_list.return_value = {"threads": [{"id": "t1"}]}
            mock_get_thread.return_value = {"id": "t1", "messages": []}
            mock_process.return_value = {"emails": 12, "contacts": 3, "attachments": 0}

            await engine.full_sync()

            mock_cl.assert_called_once()
            call_args = mock_cl.call_args[0]
            assert call_args[0] == "sync_complete"
            assert "emails" in call_args[1]
            assert "threads" in call_args[1]

    @pytest.mark.asyncio
    async def test_incremental_sync_calls_changelog(self):
        from src.gmail.sync import SyncEngine

        engine = SyncEngine()
        engine.status["last_history_id"] = "999"

        with patch.object(engine.client, "list_history", new_callable=AsyncMock) as mock_history, \
             patch.object(engine.client, "get_thread", new_callable=AsyncMock) as mock_get, \
             patch.object(engine, "_process_thread", new_callable=AsyncMock) as mock_process, \
             patch("src.gmail.sync.publish_event", new_callable=AsyncMock), \
             patch("src.gmail.sync._append_changelog") as mock_cl:

            mock_history.return_value = {
                "history": [{"messagesAdded": [{"message": {"threadId": "th1"}}]}],
                "historyId": "1000",
            }
            mock_get.return_value = {"id": "th1", "messages": []}
            mock_process.return_value = {"emails": 2, "contacts": 1, "attachments": 0}

            await engine.incremental_sync()

            mock_cl.assert_called_once()
            call_args = mock_cl.call_args[0]
            assert call_args[0] == "sync_complete"

    @pytest.mark.asyncio
    async def test_full_sync_does_not_call_changelog_on_error(self):
        from src.gmail.sync import SyncEngine

        engine = SyncEngine()

        with patch.object(engine.client, "get_profile", new_callable=AsyncMock) as mock_profile, \
             patch("src.gmail.sync._append_changelog") as mock_cl:

            mock_profile.side_effect = RuntimeError("Gmail API down")

            with pytest.raises(RuntimeError):
                await engine.full_sync()

            mock_cl.assert_not_called()
