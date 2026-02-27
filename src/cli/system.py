"""System CLI commands — sync, stats, status."""

import json
import os

import click

from src.cli.api_client import api_get, api_post
from src.cli.formatters import format_json, format_result, json_option

# Absolute path to the SYSTEM_BRIEF.md context file.
_SYSTEM_BRIEF_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "context", "SYSTEM_BRIEF.md")
)


@click.command("sync")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def sync_cmd(url, as_json):
    """Trigger an email sync."""
    data = api_post("/api/sync", url)

    # Show status
    status = api_get("/api/sync/status", url)

    if as_json:
        format_result({"message": data["message"], "status": status}, as_json=True)
        return

    click.echo(data["message"])
    format_json(status)


@click.command("stats")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def stats_cmd(url, as_json):
    """Show storage and email stats."""
    data = api_get("/api/stats", url)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Threads:     {data['total_threads']}")
    click.echo(f"Emails:      {data['total_emails']}")
    click.echo(f"Contacts:    {data['total_contacts']}")
    click.echo(f"Attachments: {data['total_attachments']}")
    click.echo(f"Unread:      {data['unread_emails']}")
    click.echo(f"DB Size:     {data['db_size_mb']} MB")


@click.command("status")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
def status_cmd(as_json: bool, url: str) -> None:
    """System overview — health, inbox snapshot, pending items."""
    health = api_get("/api/health", url)
    stats = api_get("/api/stats", url)

    if as_json:
        envelope = {
            "ok": health.get("status") == "ok",
            "data": {
                "health": health,
                "stats": stats,
            },
        }
        click.echo(json.dumps(envelope, indent=2, default=str))
        return

    # Human-readable summary
    db_status = "OK" if health.get("db") else "FAIL"
    redis_status = "OK" if health.get("redis") else "FAIL"
    overall = health.get("status", "unknown").upper()

    click.echo(f"GhostPost status: {overall}")
    click.echo(f"  DB:    {db_status}")
    click.echo(f"  Redis: {redis_status}")
    click.echo("")
    click.echo("Inbox snapshot:")
    click.echo(f"  Threads:     {stats.get('total_threads', 'N/A')}")
    click.echo(f"  Emails:      {stats.get('total_emails', 'N/A')}")
    click.echo(f"  Unread:      {stats.get('unread_emails', 'N/A')}")
    click.echo(f"  Contacts:    {stats.get('total_contacts', 'N/A')}")
    click.echo(f"  Attachments: {stats.get('total_attachments', 'N/A')}")
    click.echo(f"  DB Size:     {stats.get('db_size_mb', 'N/A')} MB")

    # Print the living system brief if it exists — gives the agent a narrative snapshot.
    if os.path.isfile(_SYSTEM_BRIEF_PATH):
        click.echo("")
        click.echo("--- SYSTEM_BRIEF.md ---")
        with open(_SYSTEM_BRIEF_PATH) as brief_file:
            click.echo(brief_file.read())
