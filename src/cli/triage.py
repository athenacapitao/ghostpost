"""Triage CLI command — single entry point for agent decision-making."""

import click

from src.cli.api_client import api_get
from src.cli.formatters import format_result, json_option

# Priority label ordering for human display
_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


@click.command("triage")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option(
    "--limit",
    default=10,
    show_default=True,
    type=click.IntRange(1, 50),
    help="Maximum number of actions to return.",
)
@json_option
def triage_cmd(url: str, limit: int, as_json: bool) -> None:
    """Show prioritized triage actions for the agent to execute next."""
    data = api_get("/api/triage/", url, limit=limit)

    if as_json:
        format_result(data, as_json=True)
        return

    # --- Human-readable output ---
    summary = data.get("summary", {})
    actions = data.get("actions", [])
    timestamp = data.get("timestamp", "")

    click.echo(f"GhostPost Triage  [{timestamp}]")
    click.echo("")

    # Inbox snapshot
    click.echo("Inbox snapshot:")
    click.echo(f"  Threads:            {summary.get('total_threads', 0)}")
    click.echo(f"  Unread:             {summary.get('unread', 0)}")
    click.echo(f"  New (untriaged):    {summary.get('new_threads', 0)}")
    click.echo(f"  Pending drafts:     {summary.get('pending_drafts', 0)}")
    click.echo(f"  Overdue follow-ups: {summary.get('overdue_threads', 0)}")
    click.echo(f"  Security incidents: {summary.get('security_incidents', 0)}")

    by_state = summary.get("by_state", {})
    if by_state:
        click.echo("")
        click.echo("By state:")
        for state, count in sorted(by_state.items()):
            click.echo(f"  {state:<20} {count}")

    if not actions:
        click.echo("")
        click.echo("No actions required — inbox is clear.")
        return

    click.echo("")
    click.echo(f"Actions ({len(actions)}):")
    click.echo("-" * 70)

    for idx, action in enumerate(actions, start=1):
        priority = action.get("priority", "low").upper()
        action_type = action.get("action", "")
        reason = action.get("reason", "")
        command = action.get("command", "")

        click.echo(f"{idx:>2}. [{priority}] {action_type}")
        click.echo(f"     {reason}")
        click.echo(f"     $ {command}")

    click.echo("")
    click.echo(f"Run the commands above to clear the queue. {len(actions)} item(s) pending.")
