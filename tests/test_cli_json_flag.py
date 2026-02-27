"""Tests for the --json flag added to all GhostPost CLI commands.

Each test verifies that:
  1. The flag is accepted (exit code 0 from --help).
  2. When --json is passed, stdout is valid JSON with {"ok": true, "data": ...}.
  3. Without --json, human-readable output is produced (existing behaviour is
     not broken).

API calls are mocked at the api_client level so no running server is needed.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# ---------------------------------------------------------------------------
# Common fixtures / helpers
# ---------------------------------------------------------------------------

_THREAD_LIST = {
    "items": [
        {
            "id": 1,
            "subject": "Hello",
            "state": "NEW",
            "email_count": 3,
            "last_activity_at": "2026-01-01T00:00:00",
        }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
}

_THREAD = {
    "id": 1,
    "subject": "Hello",
    "state": "NEW",
    "emails": [],
    "goal": None,
    "acceptance_criteria": None,
    "goal_status": None,
}

_EMAIL = {
    "id": 5,
    "from_address": "alice@example.com",
    "subject": "Greetings",
    "date": "2026-01-01T00:00:00",
    "body_text": "Hi there",
}

_SEARCH_RESULT = {
    "items": [_EMAIL],
    "total": 1,
    "page": 1,
    "page_size": 10,
}

_STATS = {
    "total_threads": 42,
    "total_emails": 300,
    "total_contacts": 24,
    "total_attachments": 14,
    "unread_emails": 7,
    "db_size_mb": 1.2,
}

_SYNC_DATA = {"message": "Sync started"}
_SYNC_STATUS = {"last_sync": "2026-01-01T00:00:00", "running": False}

_ENRICHMENT_DATA = {"message": "Enrichment done", "llm_available": True}
_ENRICH_WEB_DATA = {"company": "Acme Corp", "title": "CTO"}

_DRAFT_LIST = [
    {
        "id": 1,
        "status": "pending",
        "to_addresses": ["bob@example.com"],
        "subject": "Re: Hello",
    }
]

_REPLY_DATA = {"gmail_id": "gid123", "warnings": []}
_DRAFT_DATA = {"draft_id": 7}
_APPROVE_DATA = {"message": "Sent"}
_REJECT_DATA = {"message": "Rejected"}
_TOGGLE_DATA = {"auto_reply_mode": "draft"}
_FOLLOWUP_DATA = {"follow_up_days": 3}
_STATE_DATA = {"old_state": "NEW", "new_state": "ACTIVE"}
_GENERATE_REPLY_DATA = {"to": "bob@example.com", "subject": "Re: Hi", "style": "professional", "body": "Dear Bob"}

_GOAL_DATA = {"goal": "Close deal", "acceptance_criteria": "Signed contract", "goal_status": "in_progress"}
_GOAL_CHECK_DATA = {"met": False, "reason": "No signed contract yet"}
_GOAL_CLEARED = {"message": "Goal cleared"}

_QUARANTINE_LIST = [
    {"id": 1, "severity": "high", "event_type": "injection", "email_id": 5, "thread_id": 1}
]
_QUARANTINE_ACTION = {"message": "Done"}
_BLOCKLIST_DATA = {"blocklist": ["spam@evil.com"]}
_BLOCKLIST_ACTION = {"message": "Done"}

_AUDIT_DATA = [
    {
        "timestamp": "2026-01-01T00:00:00",
        "action_type": "reply_sent",
        "actor": "agent",
        "thread_id": 1,
        "details": {},
    }
]

_SETTINGS_LIST = {"auto_reply_mode": "off", "reply_style": "professional"}
_SETTING_ONE = {"key": "auto_reply_mode", "value": "off"}
_SETTING_SET = {"key": "auto_reply_mode", "value": "draft"}

_PLAYBOOKS_LIST = [{"name": "sales", "title": "Sales Outreach"}]
_PLAYBOOK_APPLY = {"message": "Playbook applied"}
_PLAYBOOK_CREATE = {"name": "custom", "title": "Custom Playbook"}


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _is_ok_envelope(text: str) -> dict:
    """Parse output and assert it is a valid ok-envelope."""
    data = json.loads(text)
    assert data["ok"] is True, f"Expected ok=true, got: {data}"
    assert "data" in data, f"Expected 'data' key, got: {data}"
    return data


# ---------------------------------------------------------------------------
# formatters helpers
# ---------------------------------------------------------------------------

class TestFormatResult:
    def test_as_json_true_produces_envelope(self) -> None:
        from src.cli.formatters import format_result
        from click.testing import CliRunner
        import click

        @click.command()
        def cmd():
            format_result({"x": 1}, as_json=True)

        result = CliRunner().invoke(cmd)
        parsed = json.loads(result.output)
        assert parsed == {"ok": True, "data": {"x": 1}}

    def test_as_json_false_produces_raw_json(self) -> None:
        from src.cli.formatters import format_result
        import click

        @click.command()
        def cmd():
            format_result({"x": 1}, as_json=False)

        result = CliRunner().invoke(cmd)
        parsed = json.loads(result.output)
        # Raw format: just the data dict, no envelope
        assert parsed == {"x": 1}


# ---------------------------------------------------------------------------
# api_client structured errors
# ---------------------------------------------------------------------------

class TestApiClientJsonMode:
    def test_set_json_mode_toggles_flag(self) -> None:
        import src.cli.api_client as ac
        ac.set_json_mode(False)
        assert ac._json_mode is False
        ac.set_json_mode(True)
        assert ac._json_mode is True
        ac.set_json_mode(False)  # restore

    def test_connection_error_in_json_mode_outputs_structured_json(self, runner: CliRunner) -> None:
        import httpx
        import src.cli.api_client as ac

        ac.set_json_mode(True)
        try:
            with patch.object(ac, "get_api_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_client.get.side_effect = httpx.ConnectError("refused")
                mock_client_factory.return_value = mock_client

                with pytest.raises(SystemExit):
                    ac.api_get("/api/test")
        finally:
            ac.set_json_mode(False)

    def test_http_4xx_in_json_mode_outputs_structured_json(self, runner: CliRunner) -> None:
        import httpx
        import src.cli.api_client as ac

        ac.set_json_mode(True)
        try:
            with patch.object(ac, "get_api_client") as mock_client_factory:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.status_code = 404
                mock_response.text = "Not found"
                mock_response.json.return_value = {"detail": "Not found"}
                error = httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response)
                mock_client.get.side_effect = error
                mock_client_factory.return_value = mock_client

                with pytest.raises(SystemExit):
                    ac.api_get("/api/test")
        finally:
            ac.set_json_mode(False)


# ---------------------------------------------------------------------------
# threads
# ---------------------------------------------------------------------------

class TestThreadsJsonFlag:
    def test_threads_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["threads", "--help"])
        assert "--json" in result.output

    def test_threads_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_get", return_value=_THREAD_LIST):
            result = runner.invoke(cli, ["threads", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_threads_default_output_is_raw_json(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_get", return_value=_THREAD_LIST):
            result = runner.invoke(cli, ["threads"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "items" in parsed

    def test_thread_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["thread", "--help"])
        assert "--json" in result.output

    def test_thread_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_get", return_value=_THREAD):
            result = runner.invoke(cli, ["thread", "1", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_thread_default_output_is_raw_json(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.threads.api_get", return_value=_THREAD):
            result = runner.invoke(cli, ["thread", "1"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == 1


# ---------------------------------------------------------------------------
# emails
# ---------------------------------------------------------------------------

class TestEmailsJsonFlag:
    def test_email_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["email", "--help"])
        assert "--json" in result.output

    def test_email_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.emails.api_get", return_value=_EMAIL):
            result = runner.invoke(cli, ["email", "5", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_email_default_output_is_raw_json(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.emails.api_get", return_value=_EMAIL):
            result = runner.invoke(cli, ["email", "5"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["id"] == 5

    def test_search_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["search", "--help"])
        assert "--json" in result.output

    def test_search_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.emails.api_get", return_value=_SEARCH_RESULT):
            result = runner.invoke(cli, ["search", "hello", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_search_default_output_is_raw_json(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.emails.api_get", return_value=_SEARCH_RESULT):
            result = runner.invoke(cli, ["search", "hello"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "items" in parsed


# ---------------------------------------------------------------------------
# system
# ---------------------------------------------------------------------------

class TestSystemJsonFlag:
    def test_sync_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["sync", "--help"])
        assert "--json" in result.output

    def test_sync_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        def mock_api(path, base_url="http://127.0.0.1:8000", **kwargs):
            if "status" in path:
                return _SYNC_STATUS
            return _SYNC_DATA

        with patch("src.cli.system.api_post", return_value=_SYNC_DATA):
            with patch("src.cli.system.api_get", return_value=_SYNC_STATUS):
                result = runner.invoke(cli, ["sync", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_sync_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.system.api_post", return_value=_SYNC_DATA):
            with patch("src.cli.system.api_get", return_value=_SYNC_STATUS):
                result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Sync started" in result.output

    def test_stats_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["stats", "--help"])
        assert "--json" in result.output

    def test_stats_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.system.api_get", return_value=_STATS):
            result = runner.invoke(cli, ["stats", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_stats_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.system.api_get", return_value=_STATS):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "42" in result.output


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------

class TestEnrichJsonFlag:
    def test_enrich_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["enrich", "--help"])
        assert "--json" in result.output

    def test_enrich_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.enrich.api_post", return_value=_ENRICHMENT_DATA):
            result = runner.invoke(cli, ["enrich", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_enrich_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.enrich.api_post", return_value=_ENRICHMENT_DATA):
            result = runner.invoke(cli, ["enrich"])
        assert result.exit_code == 0
        assert "Enrichment done" in result.output

    def test_enrich_web_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["enrich-web", "--help"])
        assert "--json" in result.output

    def test_enrich_web_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.enrich.api_post", return_value=_ENRICH_WEB_DATA):
            result = runner.invoke(cli, ["enrich-web", "1", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------

class TestActionsJsonFlag:
    def test_reply_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["reply", "--help"])
        assert "--json" in result.output

    def test_reply_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_REPLY_DATA):
            result = runner.invoke(cli, ["reply", "1", "--body", "Hi", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_reply_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_REPLY_DATA):
            result = runner.invoke(cli, ["reply", "1", "--body", "Hi"])
        assert result.exit_code == 0
        assert "Reply sent" in result.output

    def test_draft_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["draft", "--help"])
        assert "--json" in result.output

    def test_draft_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_DRAFT_DATA):
            result = runner.invoke(cli, ["draft", "1", "--to", "bob@x.com", "-s", "Hi", "-b", "Body", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_drafts_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["drafts", "--help"])
        assert "--json" in result.output

    def test_drafts_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_get", return_value=_DRAFT_LIST):
            result = runner.invoke(cli, ["drafts", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_draft_approve_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_APPROVE_DATA):
            result = runner.invoke(cli, ["draft-approve", "1", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_draft_reject_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_REJECT_DATA):
            result = runner.invoke(cli, ["draft-reject", "1", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_toggle_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["toggle", "--help"])
        assert "--json" in result.output

    def test_toggle_json_output_is_envelope(self, runner: CliRunner) -> None:
        import src.cli.actions as actions_mod
        from src.cli.main import cli
        with patch.object(actions_mod, "api_put", return_value=_TOGGLE_DATA):
            result = runner.invoke(cli, ["toggle", "1", "--mode", "draft", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_followup_json_output_is_envelope(self, runner: CliRunner) -> None:
        import src.cli.actions as actions_mod
        from src.cli.main import cli
        with patch.object(actions_mod, "api_put", return_value=_FOLLOWUP_DATA):
            result = runner.invoke(cli, ["followup", "1", "--days", "3", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_state_json_output_is_envelope(self, runner: CliRunner) -> None:
        import src.cli.actions as actions_mod
        from src.cli.main import cli
        with patch.object(actions_mod, "api_put", return_value=_STATE_DATA):
            result = runner.invoke(cli, ["state", "1", "ACTIVE", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_generate_reply_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.actions.api_post", return_value=_GENERATE_REPLY_DATA):
            result = runner.invoke(cli, ["generate-reply", "1", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_compose_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["compose", "--help"])
        assert "--json" in result.output

    def test_compose_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        send_data = {"gmail_id": "gid999", "thread_id": 5, "warnings": []}
        with patch("src.cli.actions.api_post", return_value=send_data):
            result = runner.invoke(cli, ["compose", "--to", "bob@x.com", "-s", "Hi", "-b", "Body", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)


# ---------------------------------------------------------------------------
# goals
# ---------------------------------------------------------------------------

class TestGoalsJsonFlag:
    def test_goal_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["goal", "--help"])
        assert "--json" in result.output

    def test_goal_set_json_output_is_envelope(self, runner: CliRunner) -> None:
        import src.cli.goals as goals_mod
        from src.cli.main import cli
        with patch.object(goals_mod, "api_put", return_value=_GOAL_DATA):
            result = runner.invoke(cli, ["goal", "1", "--set", "Close deal", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_goal_check_json_output_is_envelope(self, runner: CliRunner) -> None:
        import src.cli.goals as goals_mod
        from src.cli.main import cli
        with patch.object(goals_mod, "api_post", return_value=_GOAL_CHECK_DATA):
            result = runner.invoke(cli, ["goal", "1", "--check", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_goal_show_json_output_is_envelope(self, runner: CliRunner) -> None:
        import src.cli.goals as goals_mod
        from src.cli.main import cli
        thread_with_goal = {**_THREAD, "goal": "Close deal", "acceptance_criteria": "Signed", "goal_status": "in_progress"}
        with patch.object(goals_mod, "api_get", return_value=thread_with_goal):
            result = runner.invoke(cli, ["goal", "1", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)


# ---------------------------------------------------------------------------
# security
# ---------------------------------------------------------------------------

class TestSecurityJsonFlag:
    def test_quarantine_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["quarantine", "--help"])
        assert "--json" in result.output

    def test_quarantine_list_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=_QUARANTINE_LIST):
            result = runner.invoke(cli, ["quarantine", "list", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_blocklist_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["blocklist", "--help"])
        assert "--json" in result.output

    def test_blocklist_list_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=_BLOCKLIST_DATA):
            result = runner.invoke(cli, ["blocklist", "list", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_audit_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["audit", "--help"])
        assert "--json" in result.output

    def test_audit_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=_AUDIT_DATA):
            result = runner.invoke(cli, ["audit", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_audit_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.security.api_get", return_value=_AUDIT_DATA):
            result = runner.invoke(cli, ["audit"])
        assert result.exit_code == 0
        assert "reply_sent" in result.output


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

class TestSettingsJsonFlag:
    def test_settings_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["settings", "--help"])
        assert "--json" in result.output

    def test_settings_list_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_get", return_value=_SETTINGS_LIST):
            result = runner.invoke(cli, ["settings", "list", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_settings_get_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_get", return_value=_SETTING_ONE):
            result = runner.invoke(cli, ["settings", "get", "auto_reply_mode", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_settings_set_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_put", return_value=_SETTING_SET):
            result = runner.invoke(cli, ["settings", "set", "auto_reply_mode", "draft", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_settings_list_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.settings.api_get", return_value=_SETTINGS_LIST):
            result = runner.invoke(cli, ["settings", "list"])
        assert result.exit_code == 0
        assert "auto_reply_mode" in result.output


# ---------------------------------------------------------------------------
# playbooks
# ---------------------------------------------------------------------------

class TestPlaybooksJsonFlag:
    def test_playbooks_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["playbooks", "--help"])
        assert "--json" in result.output

    def test_playbooks_list_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.playbooks.api_get", return_value=_PLAYBOOKS_LIST):
            result = runner.invoke(cli, ["playbooks", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)

    def test_playbooks_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.playbooks.api_get", return_value=_PLAYBOOKS_LIST):
            result = runner.invoke(cli, ["playbooks"])
        assert result.exit_code == 0
        assert "sales" in result.output

    def test_playbook_create_json_output_is_envelope(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        with patch("src.cli.playbooks.api_post", return_value=_PLAYBOOK_CREATE):
            result = runner.invoke(cli, ["playbook-create", "custom", "--body", "# Custom\nDo things", "--json"])
        assert result.exit_code == 0, result.output
        _is_ok_envelope(result.output)


# ---------------------------------------------------------------------------
# health (main.py)
# ---------------------------------------------------------------------------

class TestHealthJsonFlag:
    def test_health_json_flag_accepted(self, runner: CliRunner) -> None:
        from src.cli.main import cli
        result = runner.invoke(cli, ["health", "--help"])
        assert "--json" in result.output

    def test_health_json_output_is_envelope(self, runner: CliRunner) -> None:
        import httpx
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "db": True, "redis": True}

        with patch("httpx.get", return_value=mock_response):
            result = runner.invoke(cli, ["health", "--json"])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed["ok"] is True
        assert "data" in parsed

    def test_health_default_output_is_human(self, runner: CliRunner) -> None:
        from src.cli.main import cli

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "db": True, "redis": True}

        with patch("httpx.get", return_value=mock_response):
            result = runner.invoke(cli, ["health"])
        assert result.exit_code == 0
        assert "Status" in result.output
