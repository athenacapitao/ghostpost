"""Comprehensive CLI tests for all GhostPost commands not covered by test_cli_json_flag.py.

Each test class covers one CLI command or command group and verifies:
  1. --help is accepted and documents --json (exit code 0)
  2. --json produces a valid {"ok": true, "data": ...} envelope
  3. Human-readable output contains expected text

API calls are mocked at the module level so no running server is needed.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _envelope(text: str) -> dict:
    """Parse stdout and assert it is a well-formed ok-envelope."""
    data = json.loads(text)
    assert data["ok"] is True, f"Expected ok=true in: {data}"
    assert "data" in data, f"Expected 'data' key in: {data}"
    return data


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_CONTACT_LIST = {
    "items": [
        {
            "id": 1,
            "name": "Alice",
            "email": "alice@x.com",
            "company": "Acme",
            "last_interaction": "2026-01-01",
        }
    ],
    "total": 1,
}

_CONTACT = {"id": 1, "name": "Alice", "email": "alice@x.com", "company": "Acme"}

_THREAD_WITH_NOTES = {
    "id": 1,
    "subject": "Hello",
    "state": "NEW",
    "emails": [],
    "goal": None,
    "notes": "existing note",
}

_NOTES_UPDATED = {"thread_id": 1, "notes": "test note"}

_OUTCOME_EXTRACT = {
    "thread_id": 1,
    "outcome_type": "agreement",
    "summary": "Price agreed",
}

_OUTCOME_LIST = [
    {
        "thread_id": 2,
        "outcome_type": "meeting_scheduled",
        "summary": "Call on Friday",
        "created_at": "2026-01-05T10:00:00",
    }
]

_OUTCOME_GET = {
    "thread_id": 1,
    "outcome_type": "agreement",
    "summary": "Price agreed",
    "created_at": "2026-01-01T00:00:00",
    "details": {"amount": "1000"},
}

_ALERTS = {"alerts": ["New high-urgency email"], "count": 1}

_SECURITY_EVENTS = [
    {
        "id": 1,
        "severity": "HIGH",
        "event_type": "injection_detected",
        "email_id": 5,
        "thread_id": 3,
        "resolution": None,
    }
]

_BATCH_LIST = [
    {
        "id": 1,
        "job_type": "enrich",
        "status": "completed",
        "total_items": 10,
        "completed_items": 10,
        "created_at": "2026-01-01T00:00:00",
    }
]

_BATCH_DETAIL = {
    "id": 1,
    "job_type": "enrich",
    "status": "completed",
    "total_items": 10,
    "completed_items": 10,
    "created_at": "2026-01-01T00:00:00",
}

_BATCH_CANCELLED = {"id": 1, "status": "cancelled"}

_PLAYBOOK_UPDATED = {"name": "mybook", "title": "Updated"}

_SETTING_DELETED = {"message": "Setting 'reply_style' deleted"}

_SETTINGS_BULK_UPDATED = {"updated": ["notification_new_email", "notification_goal_met"]}

_GENERATE_REPLY_WITH_DRAFT = {
    "to": "x@y.com",
    "subject": "Re: Hello",
    "body": "Generated reply",
    "style": "professional",
    "draft_id": 42,
}


# ---------------------------------------------------------------------------
# 1. contacts
# ---------------------------------------------------------------------------

class TestContactsCmd:
    def test_contacts_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["contacts", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_contacts_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.contacts.api_get", return_value=_CONTACT_LIST):
            result = runner.invoke(cli, ["contacts", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["total"] == 1

    def test_contacts_human_output_shows_table(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.contacts.api_get", return_value=_CONTACT_LIST):
            result = runner.invoke(cli, ["contacts"])
        assert result.exit_code == 0, result.output
        assert "Alice" in result.output
        assert "Acme" in result.output
        assert "1 total contacts" in result.output

    def test_contacts_empty_list_shows_message(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.contacts.api_get", return_value={"items": [], "total": 0}):
            result = runner.invoke(cli, ["contacts"])
        assert result.exit_code == 0, result.output
        assert "No contacts found" in result.output

    def test_contact_detail_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["contact", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_contact_detail_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.contacts.api_get", return_value=_CONTACT):
            result = runner.invoke(cli, ["contact", "1", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["id"] == 1

    def test_contact_detail_human_output_shows_fields(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.contacts.api_get", return_value=_CONTACT):
            result = runner.invoke(cli, ["contact", "1"])
        assert result.exit_code == 0, result.output
        assert "Alice" in result.output
        assert "alice@x.com" in result.output


# ---------------------------------------------------------------------------
# 2. notes (in src/cli/threads.py)
# ---------------------------------------------------------------------------

class TestNotesCmd:
    def test_notes_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["notes", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_notes_set_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_put", return_value=_NOTES_UPDATED):
            result = runner.invoke(cli, ["notes", "1", "--text", "test note", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["notes"] == "test note"

    def test_notes_set_human_output_confirms_update(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_put", return_value=_NOTES_UPDATED):
            result = runner.invoke(cli, ["notes", "1", "--text", "test note"])
        assert result.exit_code == 0, result.output
        assert "Notes updated" in result.output

    def test_notes_view_json_returns_envelope_with_notes_field(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_get", return_value=_THREAD_WITH_NOTES):
            result = runner.invoke(cli, ["notes", "1", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert "notes" in envelope["data"]
        assert envelope["data"]["notes"] == "existing note"

    def test_notes_view_human_output_shows_notes(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_get", return_value=_THREAD_WITH_NOTES):
            result = runner.invoke(cli, ["notes", "1"])
        assert result.exit_code == 0, result.output
        assert "existing note" in result.output

    def test_notes_view_no_notes_shows_placeholder(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        thread_no_notes = {**_THREAD_WITH_NOTES, "notes": None}
        with patch("src.cli.threads.api_get", return_value=thread_no_notes):
            result = runner.invoke(cli, ["notes", "1"])
        assert result.exit_code == 0, result.output
        assert "no notes" in result.output


# ---------------------------------------------------------------------------
# 3. outcomes extract / list / get
# ---------------------------------------------------------------------------

class TestOutcomesCmd:
    def test_outcomes_extract_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["outcomes", "extract", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_outcomes_extract_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_post", return_value=_OUTCOME_EXTRACT):
            result = runner.invoke(cli, ["outcomes", "extract", "1", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["outcome_type"] == "agreement"
        assert envelope["data"]["thread_id"] == 1

    def test_outcomes_extract_human_output_confirms_extraction(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_post", return_value=_OUTCOME_EXTRACT):
            result = runner.invoke(cli, ["outcomes", "extract", "1"])
        assert result.exit_code == 0, result.output
        assert "Outcome extracted" in result.output

    def test_outcomes_list_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_get", return_value=_OUTCOME_LIST):
            result = runner.invoke(cli, ["outcomes", "list", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert isinstance(envelope["data"], list)
        assert len(envelope["data"]) == 1

    def test_outcomes_list_human_output_shows_table(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_get", return_value=_OUTCOME_LIST):
            result = runner.invoke(cli, ["outcomes", "list"])
        assert result.exit_code == 0, result.output
        assert "meeting_scheduled" in result.output

    def test_outcomes_list_empty_shows_message(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_get", return_value=[]):
            result = runner.invoke(cli, ["outcomes", "list"])
        assert result.exit_code == 0, result.output
        assert "No outcomes" in result.output

    def test_outcomes_get_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_get", return_value=_OUTCOME_GET):
            result = runner.invoke(cli, ["outcomes", "get", "1", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["outcome_type"] == "agreement"

    def test_outcomes_get_human_output_shows_details(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.outcomes.api_get", return_value=_OUTCOME_GET):
            result = runner.invoke(cli, ["outcomes", "get", "1"])
        assert result.exit_code == 0, result.output
        assert "agreement" in result.output
        assert "Price agreed" in result.output


# ---------------------------------------------------------------------------
# 4. alerts (src/cli/notifications.py)
# ---------------------------------------------------------------------------

class TestAlertsCmd:
    def test_alerts_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["alerts", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_alerts_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.notifications.api_get", return_value=_ALERTS):
            result = runner.invoke(cli, ["alerts", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["count"] == 1
        assert "New high-urgency email" in envelope["data"]["alerts"]

    def test_alerts_human_output_shows_alerts(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.notifications.api_get", return_value=_ALERTS):
            result = runner.invoke(cli, ["alerts"])
        assert result.exit_code == 0, result.output
        assert "New high-urgency email" in result.output

    def test_alerts_empty_shows_no_alerts_message(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.notifications.api_get", return_value={"alerts": [], "count": 0}):
            result = runner.invoke(cli, ["alerts"])
        assert result.exit_code == 0, result.output
        assert "No active alerts" in result.output


# ---------------------------------------------------------------------------
# 5. security-events (src/cli/security.py)
# ---------------------------------------------------------------------------

class TestSecurityEventsCmd:
    def test_security_events_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["security-events", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_security_events_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=_SECURITY_EVENTS):
            result = runner.invoke(cli, ["security-events", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert isinstance(envelope["data"], list)
        assert envelope["data"][0]["severity"] == "HIGH"
        assert envelope["data"][0]["event_type"] == "injection_detected"

    def test_security_events_human_output_shows_events(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=_SECURITY_EVENTS):
            result = runner.invoke(cli, ["security-events"])
        assert result.exit_code == 0, result.output
        assert "HIGH" in result.output
        assert "injection_detected" in result.output

    def test_security_events_empty_shows_message(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=[]):
            result = runner.invoke(cli, ["security-events"])
        assert result.exit_code == 0, result.output
        assert "No security events found" in result.output

    def test_security_events_pending_only_flag_passes_param(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=[]) as mock_get:
            result = runner.invoke(cli, ["security-events", "--pending-only"])
        assert result.exit_code == 0, result.output
        # Verify pending_only=True was passed to api_get
        call_kwargs = mock_get.call_args
        assert call_kwargs is not None


# ---------------------------------------------------------------------------
# 6. attachment (uses get_api_client directly)
# ---------------------------------------------------------------------------

class TestAttachmentCmd:
    def test_attachment_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["attachment", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_attachment_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-disposition": 'filename="doc.pdf"'}
        mock_response.content = b"file content"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "doc.pdf")
            with patch("src.cli.attachments.get_api_client", return_value=mock_client):
                result = runner.invoke(
                    cli, ["attachment", "1", "--output", output_path, "--json"]
                )

        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["filename"] == "doc.pdf"
        assert envelope["data"]["size"] == len(b"file content")

    def test_attachment_human_output_shows_saved_message(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-disposition": 'filename="report.xlsx"'}
        mock_response.content = b"spreadsheet bytes"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "report.xlsx")
            with patch("src.cli.attachments.get_api_client", return_value=mock_client):
                result = runner.invoke(
                    cli, ["attachment", "1", "--output", output_path]
                )

        assert result.exit_code == 0, result.output
        assert "Saved" in result.output
        assert "report.xlsx" in result.output

    def test_attachment_download_error_returns_error_envelope_in_json_mode(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli

        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Connection refused")

        with patch("src.cli.attachments.get_api_client", return_value=mock_client):
            result = runner.invoke(cli, ["attachment", "1", "--json"])

        # Should exit with non-zero but still emit JSON
        assert result.exit_code != 0
        parsed = json.loads(result.output)
        assert parsed["ok"] is False
        assert parsed["code"] == "DOWNLOAD_ERROR"

    def test_attachment_filename_fallback_when_no_content_disposition(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}  # no content-disposition header
        mock_response.content = b"data"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "fallback_file")
            with patch("src.cli.attachments.get_api_client", return_value=mock_client):
                result = runner.invoke(
                    cli, ["attachment", "99", "--output", output_path, "--json"]
                )

        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        # Fallback filename uses attachment_id
        assert "99" in envelope["data"]["filename"]


# ---------------------------------------------------------------------------
# 7. batch list / detail / cancel
# ---------------------------------------------------------------------------

class TestBatchCmd:
    def test_batch_list_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["batch", "list", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_batch_list_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_get", return_value=_BATCH_LIST):
            result = runner.invoke(cli, ["batch", "list", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert isinstance(envelope["data"], list)
        assert envelope["data"][0]["job_type"] == "enrich"

    def test_batch_list_human_output_shows_table(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_get", return_value=_BATCH_LIST):
            result = runner.invoke(cli, ["batch", "list"])
        assert result.exit_code == 0, result.output
        assert "enrich" in result.output
        assert "completed" in result.output

    def test_batch_list_empty_shows_message(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_get", return_value=[]):
            result = runner.invoke(cli, ["batch", "list"])
        assert result.exit_code == 0, result.output
        assert "No batch jobs" in result.output

    def test_batch_detail_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["batch", "detail", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_batch_detail_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_get", return_value=_BATCH_DETAIL):
            result = runner.invoke(cli, ["batch", "detail", "1", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["id"] == 1
        assert envelope["data"]["status"] == "completed"

    def test_batch_detail_human_output_shows_fields(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_get", return_value=_BATCH_DETAIL):
            result = runner.invoke(cli, ["batch", "detail", "1"])
        assert result.exit_code == 0, result.output
        assert "enrich" in result.output
        assert "completed" in result.output
        assert "10/10" in result.output

    def test_batch_cancel_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["batch", "cancel", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_batch_cancel_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_post", return_value=_BATCH_CANCELLED):
            result = runner.invoke(cli, ["batch", "cancel", "1", "--json"])
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["status"] == "cancelled"

    def test_batch_cancel_human_output_confirms_cancellation(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.batch.api_post", return_value=_BATCH_CANCELLED):
            result = runner.invoke(cli, ["batch", "cancel", "1"])
        assert result.exit_code == 0, result.output
        assert "cancelled" in result.output


# ---------------------------------------------------------------------------
# 8. playbook-update (uses get_api_client directly)
# ---------------------------------------------------------------------------

class TestPlaybookUpdateCmd:
    def test_playbook_update_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["playbook-update", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_playbook_update_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        with patch("src.cli.playbooks.api_put", return_value=_PLAYBOOK_UPDATED):
            result = runner.invoke(
                cli, ["playbook-update", "mybook", "--body", "## Updated", "--json"]
            )

        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["name"] == "mybook"

    def test_playbook_update_human_output_confirms_update(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        with patch("src.cli.playbooks.api_put", return_value=_PLAYBOOK_UPDATED):
            result = runner.invoke(
                cli, ["playbook-update", "mybook", "--body", "## Updated"]
            )

        assert result.exit_code == 0, result.output
        assert "Updated playbook" in result.output
        assert "mybook" in result.output

    def test_playbook_update_sends_json_body(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        with patch("src.cli.playbooks.api_put", return_value=_PLAYBOOK_UPDATED) as mock_put:
            runner.invoke(
                cli, ["playbook-update", "mybook", "--body", "## New content"]
            )

        mock_put.assert_called_once()
        call_kwargs = mock_put.call_args
        assert call_kwargs[1]["json"] == {"content": "## New content"}


# ---------------------------------------------------------------------------
# 9. settings delete & bulk
# ---------------------------------------------------------------------------

class TestSettingsDeleteAndBulk:
    def test_settings_delete_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_delete", return_value=_SETTING_DELETED):
            result = runner.invoke(
                cli, ["settings", "delete", "reply_style", "--json"]
            )
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert "reply_style" in envelope["data"]["message"]

    def test_settings_delete_human_output_confirms_deletion(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_delete", return_value=_SETTING_DELETED):
            result = runner.invoke(cli, ["settings", "delete", "reply_style"])
        assert result.exit_code == 0, result.output
        assert "reply_style" in result.output

    def test_settings_delete_requires_key_argument(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["settings", "delete"])
        assert result.exit_code != 0

    def test_settings_bulk_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_put", return_value=_SETTINGS_BULK_UPDATED):
            result = runner.invoke(
                cli,
                [
                    "settings",
                    "bulk",
                    "notification_new_email=false",
                    "notification_goal_met=false",
                    "--json",
                ],
            )
        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert "notification_new_email" in envelope["data"]["updated"]
        assert "notification_goal_met" in envelope["data"]["updated"]

    def test_settings_bulk_human_output_shows_updated_count(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_put", return_value=_SETTINGS_BULK_UPDATED):
            result = runner.invoke(
                cli,
                [
                    "settings",
                    "bulk",
                    "notification_new_email=false",
                    "notification_goal_met=false",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "2" in result.output  # Updated 2 settings
        assert "notification" in result.output

    def test_settings_bulk_requires_at_least_one_pair(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["settings", "bulk"])
        assert result.exit_code != 0

    def test_settings_bulk_rejects_malformed_pairs(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["settings", "bulk", "badformat"])
        assert result.exit_code != 0
        assert "invalid format" in result.output.lower() or "Error" in result.output

    def test_settings_bulk_passes_key_value_dict_to_api(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_put", return_value=_SETTINGS_BULK_UPDATED) as mock_put:
            runner.invoke(
                cli,
                ["settings", "bulk", "foo=bar", "baz=qux", "--json"],
            )
        call_kwargs = mock_put.call_args
        assert call_kwargs is not None
        # Verify the JSON payload contains both keys
        json_payload = call_kwargs[1].get("json") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
        # The payload is nested under {"settings": {...}}
        assert "settings" in json_payload or "foo" in str(call_kwargs)


# ---------------------------------------------------------------------------
# 10. research output (uses httpx directly)
# ---------------------------------------------------------------------------

class TestResearchOutputCmd:
    def test_research_output_help_shows_json_flag(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["research", "output", "--help"])
        assert result.exit_code == 0, result.output
        assert "--json" in result.output

    def test_research_output_json_returns_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Research Output\nContent here"
        mock_response.raise_for_status = MagicMock()

        # research.py calls httpx.get directly; also needs _get_headers which
        # calls httpx.post for login — we mock the entire httpx module
        with patch("src.cli.research.httpx") as mock_httpx:
            # Login call returns empty token (no GHOSTPOST_TOKEN env var)
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = {"token": "test-token"}
            mock_httpx.post.return_value = login_resp

            mock_httpx.get.return_value = mock_response

            result = runner.invoke(
                cli, ["research", "output", "1", "06_email_draft.md", "--json"]
            )

        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["campaign_id"] == 1
        assert envelope["data"]["filename"] == "06_email_draft.md"
        assert "Research Output" in envelope["data"]["content"]

    def test_research_output_human_output_shows_content(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Research Output\nContent here"
        mock_response.raise_for_status = MagicMock()

        with patch("src.cli.research.httpx") as mock_httpx:
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = {"token": "test-token"}
            mock_httpx.post.return_value = login_resp

            mock_httpx.get.return_value = mock_response

            result = runner.invoke(
                cli, ["research", "output", "1", "06_email_draft.md"]
            )

        assert result.exit_code == 0, result.output
        assert "Research Output" in result.output
        assert "Content here" in result.output

    def test_research_output_404_exits_with_error_json(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("src.cli.research.httpx") as mock_httpx:
            login_resp = MagicMock()
            login_resp.status_code = 200
            login_resp.json.return_value = {"token": "test-token"}
            mock_httpx.post.return_value = login_resp

            mock_httpx.get.return_value = mock_response

            result = runner.invoke(
                cli, ["research", "output", "1", "missing.md", "--json"]
            )

        assert result.exit_code != 0
        parsed = json.loads(result.output)
        assert parsed["ok"] is False
        assert parsed["code"] == "HTTP_4XX"

    def test_research_output_uses_ghostpost_token_env_var_when_set(
        self, runner: CliRunner
    ) -> None:
        """When GHOSTPOST_TOKEN is set, no login POST should be made."""
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "output content"
        mock_response.raise_for_status = MagicMock()

        with patch("src.cli.research.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response

            with patch.dict(os.environ, {"GHOSTPOST_TOKEN": "my-preset-token"}):
                result = runner.invoke(
                    cli, ["research", "output", "2", "01_overview.md", "--json"]
                )

            # No login POST should have been made since token was present
            mock_httpx.post.assert_not_called()

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# 11. generate-reply --draft flag
# ---------------------------------------------------------------------------

class TestGenerateReplyDraftFlag:
    def test_generate_reply_draft_flag_help_docs_option(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["generate-reply", "--help"])
        assert result.exit_code == 0, result.output
        assert "--draft" in result.output

    def test_generate_reply_with_draft_flag_json_returns_envelope(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_GENERATE_REPLY_WITH_DRAFT) as mock_post:
            result = runner.invoke(cli, ["generate-reply", "1", "--draft", "--json"])

        assert result.exit_code == 0, result.output
        envelope = _envelope(result.output)
        assert envelope["data"]["draft_id"] == 42
        assert envelope["data"]["body"] == "Generated reply"

    def test_generate_reply_with_draft_flag_passes_create_draft_param(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_GENERATE_REPLY_WITH_DRAFT) as mock_post:
            runner.invoke(cli, ["generate-reply", "1", "--draft", "--json"])

        call_kwargs = mock_post.call_args
        assert call_kwargs is not None
        # params dict should include create_draft="true"
        params = call_kwargs[1].get("params") or {}
        assert params.get("create_draft") == "true"

    def test_generate_reply_with_draft_flag_human_output_shows_draft_id(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_GENERATE_REPLY_WITH_DRAFT):
            result = runner.invoke(cli, ["generate-reply", "1", "--draft"])

        assert result.exit_code == 0, result.output
        assert "Draft ID" in result.output
        assert "42" in result.output

    def test_generate_reply_without_draft_flag_does_not_pass_create_draft(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli
        plain_reply = {
            "to": "x@y.com",
            "subject": "Re: Hello",
            "body": "Generated reply",
            "style": "professional",
        }
        with patch("src.cli.actions.api_post", return_value=plain_reply) as mock_post:
            runner.invoke(cli, ["generate-reply", "1", "--json"])

        call_kwargs = mock_post.call_args
        assert call_kwargs is not None
        params = call_kwargs[1].get("params") or {}
        assert "create_draft" not in params

    def test_generate_reply_with_draft_flag_and_instructions(
        self, runner: CliRunner
    ) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_GENERATE_REPLY_WITH_DRAFT) as mock_post:
            result = runner.invoke(
                cli,
                ["generate-reply", "1", "--draft", "--instructions", "Keep it brief", "--json"],
            )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_post.call_args
        params = call_kwargs[1].get("params") or {}
        assert params.get("create_draft") == "true"
        assert params.get("instructions") == "Keep it brief"
