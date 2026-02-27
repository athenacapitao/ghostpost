"""CLI commands for security — quarantine, blocklist, audit."""

import click

from src.cli.api_client import api_get, api_post, api_delete
from src.cli.formatters import format_result, json_option


@click.command("quarantine")
@click.argument("action", type=click.Choice(["list", "approve", "dismiss"]))
@click.argument("event_id", type=int, required=False)
@json_option
def quarantine_cmd(action: str, event_id: int | None, as_json: bool) -> None:
    """Manage quarantined emails."""
    if action == "list":
        data = api_get("/api/security/quarantine")
        if as_json:
            format_result(data, as_json=True)
            return
        if not data:
            click.echo("No quarantined items.")
            return
        for e in data:
            click.echo(f"  #{e['id']}  [{e['severity']}] {e['event_type']}  Email: {e.get('email_id', '-')}  Thread: {e.get('thread_id', '-')}")
    elif action == "approve":
        if not event_id:
            click.echo("Error: event_id required for approve", err=True)
            return
        data = api_post(f"/api/security/quarantine/{event_id}/approve")
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(data.get("message", "Done"))
    elif action == "dismiss":
        if not event_id:
            click.echo("Error: event_id required for dismiss", err=True)
            return
        data = api_post(f"/api/security/quarantine/{event_id}/dismiss")
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(data.get("message", "Done"))


@click.command("blocklist")
@click.argument("action", type=click.Choice(["list", "add", "remove"]))
@click.argument("email", required=False)
@json_option
def blocklist_cmd(action: str, email: str | None, as_json: bool) -> None:
    """Manage email blocklist."""
    if action == "list":
        data = api_get("/api/security/blocklist")
        if as_json:
            format_result(data, as_json=True)
            return
        bl = data.get("blocklist", [])
        if not bl:
            click.echo("Blocklist is empty.")
            return
        for addr in bl:
            click.echo(f"  {addr}")
    elif action == "add":
        if not email:
            click.echo("Error: email required for add", err=True)
            return
        data = api_post("/api/security/blocklist", json={"email": email})
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(data.get("message", "Done"))
    elif action == "remove":
        if not email:
            click.echo("Error: email required for remove", err=True)
            return
        data = api_delete("/api/security/blocklist", json={"email": email})
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(data.get("message", "Done"))


@click.command("security-events")
@click.option("--pending-only", is_flag=True, help="Show only pending events")
@click.option("--limit", default=50, type=int, help="Max events to show")
@json_option
def security_events_cmd(pending_only: bool, limit: int, as_json: bool) -> None:
    """List all security events."""
    data = api_get("/api/security/events", pending_only=pending_only, limit=limit)

    if as_json:
        format_result(data, as_json=True)
        return

    if not data:
        click.echo("No security events found.")
        return
    for e in data:
        status = f" [{e.get('resolution', 'pending')}]" if e.get('resolution') else ""
        click.echo(
            f"  #{e['id']}  [{e['severity']}] {e['event_type']}  "
            f"Email: {e.get('email_id', '-')}  Thread: {e.get('thread_id', '-')}{status}"
        )


@click.command("audit")
@click.option("--hours", default=24, type=int, help="Look back this many hours")
@click.option("--limit", default=20, type=int, help="Max entries to show")
@json_option
def audit_cmd(hours: int, limit: int, as_json: bool) -> None:
    """Show recent audit log entries."""
    data = api_get("/api/audit", hours=hours, limit=limit)

    if as_json:
        format_result(data, as_json=True)
        return

    if not data:
        click.echo("No audit entries found.")
        return
    for entry in data:
        ts = entry.get("timestamp", "")[:19]
        action = entry.get("action_type", "unknown")
        actor = entry.get("actor", "system")
        thread = entry.get("thread_id") or "-"
        click.echo(f"  {ts}  [{actor}] {action}  thread={thread}")
        details = entry.get("details")
        if details:
            for k, v in details.items():
                click.echo(f"    {k}: {v}")
