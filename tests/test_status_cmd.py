"""Unit tests for the `ghostpost status` CLI command."""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_HEALTH_OK = {"status": "ok", "db": True, "redis": True}
_HEALTH_DEGRADED = {"status": "degraded", "db": True, "redis": False}

_STATS = {
    "total_threads": 42,
    "total_emails": 300,
    "unread_emails": 7,
    "total_contacts": 24,
    "total_attachments": 14,
    "db_size_mb": 1.2,
}


def _invoke_status(extra_args: list[str] | None = None, brief_content: str | None = None):
    """Invoke the status command with api_get mocked.

    Returns (result, runner) so callers can inspect output and exit code.
    """
    from src.cli.main import cli

    runner = CliRunner()
    args = ["status"] + (extra_args or [])

    def mock_api_get(path: str, base_url: str = "http://127.0.0.1:8000", **params):
        if path == "/api/health":
            return _HEALTH_OK
        if path == "/api/stats":
            return _STATS
        raise ValueError(f"Unexpected api_get path: {path}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        brief_path = os.path.join(tmp_dir, "SYSTEM_BRIEF.md")
        if brief_content is not None:
            with open(brief_path, "w") as f:
                f.write(brief_content)

        with patch("src.cli.system.api_get", side_effect=mock_api_get):
            with patch("src.cli.system._SYSTEM_BRIEF_PATH", brief_path):
                result = runner.invoke(cli, args)

    return result


# ---------------------------------------------------------------------------
# Human-readable (default) mode
# ---------------------------------------------------------------------------

class TestStatusCmdHumanMode:
    def test_exits_zero_on_success(self) -> None:
        result = _invoke_status()
        assert result.exit_code == 0, result.output

    def test_shows_overall_status(self) -> None:
        result = _invoke_status()
        assert "OK" in result.output

    def test_shows_db_and_redis_status(self) -> None:
        result = _invoke_status()
        assert "DB:" in result.output
        assert "Redis:" in result.output

    def test_shows_thread_count(self) -> None:
        result = _invoke_status()
        assert "42" in result.output

    def test_shows_unread_count(self) -> None:
        result = _invoke_status()
        assert "7" in result.output

    def test_shows_email_count(self) -> None:
        result = _invoke_status()
        assert "300" in result.output

    def test_shows_db_size(self) -> None:
        result = _invoke_status()
        assert "1.2" in result.output

    def test_shows_inbox_snapshot_heading(self) -> None:
        result = _invoke_status()
        assert "Inbox snapshot" in result.output or "inbox" in result.output.lower()

    def test_prints_system_brief_when_file_exists(self) -> None:
        result = _invoke_status(brief_content="## Agent Brief\nAll systems nominal.")
        assert "SYSTEM_BRIEF.md" in result.output
        assert "All systems nominal." in result.output

    def test_omits_brief_section_when_file_missing(self) -> None:
        # No brief_content passed → file does not exist
        result = _invoke_status()
        assert "SYSTEM_BRIEF.md" not in result.output

    def test_degraded_redis_shown(self) -> None:
        """When Redis is down, the Redis line should show FAIL."""
        from src.cli.main import cli

        runner = CliRunner()

        def mock_api_get_degraded(path: str, base_url: str = "http://127.0.0.1:8000", **params):
            if path == "/api/health":
                return _HEALTH_DEGRADED
            return _STATS

        with tempfile.TemporaryDirectory() as tmp_dir:
            brief_path = os.path.join(tmp_dir, "SYSTEM_BRIEF.md")
            with patch("src.cli.system.api_get", side_effect=mock_api_get_degraded):
                with patch("src.cli.system._SYSTEM_BRIEF_PATH", brief_path):
                    result = runner.invoke(cli, ["status"])

        assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# JSON mode
# ---------------------------------------------------------------------------

class TestStatusCmdJsonMode:
    def test_exits_zero_on_success(self) -> None:
        result = _invoke_status(["--json"])
        assert result.exit_code == 0, result.output

    def test_output_is_valid_json(self) -> None:
        result = _invoke_status(["--json"])
        parsed = json.loads(result.output)
        assert isinstance(parsed, dict)

    def test_ok_field_is_true_when_healthy(self) -> None:
        result = _invoke_status(["--json"])
        parsed = json.loads(result.output)
        assert parsed["ok"] is True

    def test_ok_field_is_false_when_degraded(self) -> None:
        from src.cli.main import cli

        runner = CliRunner()

        def mock_api_get_degraded(path: str, base_url: str = "http://127.0.0.1:8000", **params):
            if path == "/api/health":
                return _HEALTH_DEGRADED
            return _STATS

        with tempfile.TemporaryDirectory() as tmp_dir:
            brief_path = os.path.join(tmp_dir, "SYSTEM_BRIEF.md")
            with patch("src.cli.system.api_get", side_effect=mock_api_get_degraded):
                with patch("src.cli.system._SYSTEM_BRIEF_PATH", brief_path):
                    result = runner.invoke(cli, ["status", "--json"])

        parsed = json.loads(result.output)
        assert parsed["ok"] is False

    def test_data_contains_health_key(self) -> None:
        result = _invoke_status(["--json"])
        parsed = json.loads(result.output)
        assert "health" in parsed["data"]

    def test_data_contains_stats_key(self) -> None:
        result = _invoke_status(["--json"])
        parsed = json.loads(result.output)
        assert "stats" in parsed["data"]

    def test_health_payload_matches_api_response(self) -> None:
        result = _invoke_status(["--json"])
        parsed = json.loads(result.output)
        assert parsed["data"]["health"] == _HEALTH_OK

    def test_stats_payload_matches_api_response(self) -> None:
        result = _invoke_status(["--json"])
        parsed = json.loads(result.output)
        assert parsed["data"]["stats"] == _STATS

    def test_json_mode_does_not_include_brief(self) -> None:
        """In JSON mode, the SYSTEM_BRIEF is not included in the output."""
        result = _invoke_status(["--json"], brief_content="## Brief content")
        # Output must be parseable JSON — brief text would break that
        parsed = json.loads(result.output)
        assert "Brief content" not in result.output
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------

class TestStatusCmdHelp:
    def test_help_exits_zero(self) -> None:
        from src.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_help_describes_command(self) -> None:
        from src.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        # The docstring from status_cmd should appear
        assert "status" in result.output.lower() or "overview" in result.output.lower()
