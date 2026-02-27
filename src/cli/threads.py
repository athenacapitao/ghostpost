"""Thread CLI commands."""

import click

from src.cli.api_client import api_get, api_put
from src.cli.formatters import format_json, format_result, format_table, json_option


@click.command("threads")
@click.option("--state", help="Filter by state (NEW, ACTIVE, WAITING_REPLY, etc.)")
@click.option("--limit", default=20, help="Number of results")
@click.option("--table", "as_table", is_flag=True, help="Table output")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def threads_cmd(state, limit, as_table, url, as_json):
    """List email threads."""
    params = {"page_size": limit}
    if state:
        params["state"] = state
    data = api_get("/api/threads", url, **params)

    if as_json:
        format_result(data, as_json=True)
    elif as_table:
        headers = ["ID", "Subject", "State", "Emails", "Last Activity"]
        rows = [
            [
                t["id"],
                (t["subject"] or "")[:50],
                t["state"],
                t["email_count"],
                (t["last_activity_at"] or "")[:16],
            ]
            for t in data["items"]
        ]
        format_table(headers, rows)
        click.echo(f"\n{data['total']} total threads")
    else:
        format_json(data)


@click.command("thread")
@click.argument("thread_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def thread_cmd(thread_id, url, as_json):
    """Show a thread with all its emails."""
    data = api_get(f"/api/threads/{thread_id}", url)
    format_result(data, as_json=as_json)


@click.command("notes")
@click.argument("thread_id", type=int)
@click.option("--text", "-t", default=None, help="Notes text to set (omit to view current notes)")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def notes_cmd(thread_id: int, text: str | None, url: str, as_json: bool) -> None:
    """View or set notes on a thread."""
    if text is not None:
        data = api_put(f"/api/threads/{thread_id}/notes", url, json={"notes": text})
        if as_json:
            format_result(data, as_json=True)
            return
        click.echo(f"Notes updated for thread #{thread_id}")
    else:
        data = api_get(f"/api/threads/{thread_id}", url)
        if as_json:
            format_result({"thread_id": thread_id, "notes": data.get("notes")}, as_json=True)
            return
        notes = data.get("notes") or "(no notes)"
        click.echo(f"Thread #{thread_id} notes: {notes}")
