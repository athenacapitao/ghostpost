"""CLI tool validation tests.

Tests CLI commands work correctly end-to-end by invoking them through
Click's test runner.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# CLI import and basic structure
# ---------------------------------------------------------------------------

class TestCLIStructure:
    def test_cli_imports(self):
        """CLI module imports without error."""
        from src.cli.main import cli
        assert cli is not None

    def test_cli_help(self):
        """CLI --help works."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ghostpost" in result.output.lower() or "Usage" in result.output

    def test_cli_has_health_command(self):
        """CLI has 'health' command."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "--help"])
        assert result.exit_code == 0

    def test_cli_has_threads_command(self):
        """CLI has 'threads' command."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["threads", "--help"])
        assert result.exit_code == 0

    def test_cli_has_search_command(self):
        """CLI has 'search' command."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0

    def test_cli_has_stats_command(self):
        """CLI has 'stats' command."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0

    def test_cli_has_sync_command(self):
        """CLI has 'sync' command."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# CLI error handling
# ---------------------------------------------------------------------------

class TestCLIErrorHandling:
    def test_cli_unknown_command(self):
        """Unknown command should show error."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["nonexistent_command"])
        assert result.exit_code != 0

    def test_cli_thread_without_id(self):
        """'thread' without ID should show usage error."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["thread"])
        # Should either show error or help
        assert result.exit_code != 0 or "Usage" in result.output or "Error" in result.output


# ---------------------------------------------------------------------------
# API client module
# ---------------------------------------------------------------------------

class TestAPIClient:
    def test_api_client_imports(self):
        """API client module imports without error."""
        from src.cli.api_client import get_api_client, api_get, api_post
        assert callable(get_api_client)
        assert callable(api_get)
        assert callable(api_post)

    def test_formatters_import(self):
        """Formatters module imports without error."""
        from src.cli.formatters import format_table, format_json
        assert callable(format_table)
        assert callable(format_json)


# ---------------------------------------------------------------------------
# Playbook CLI commands
# ---------------------------------------------------------------------------

class TestPlaybookCLI:
    def test_playbooks_help(self):
        """'playbooks' command has help."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["playbooks", "--help"])
        assert result.exit_code == 0

    def test_blocklist_help(self):
        """'blocklist' command has help."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["blocklist", "--help"])
        assert result.exit_code == 0

    def test_settings_help(self):
        """'settings' command has help."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["settings", "--help"])
        assert result.exit_code == 0

    def test_audit_help(self):
        """'audit' command has help."""
        from src.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["audit", "--help"])
        assert result.exit_code == 0
