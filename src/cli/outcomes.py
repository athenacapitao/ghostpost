"""CLI commands for viewing completed thread outcomes."""

import click

from src.cli.api_client import api_get, api_post
from src.cli.formatters import format_result, format_table, json_option


@click.group("outcomes")
def outcomes_group() -> None:
    """View completed thread outcomes."""
    pass


@outcomes_group.command("list")
@click.option("--limit", default=20, type=int, help="Max outcomes to show")
@json_option
def list_outcomes(limit: int, as_json: bool) -> None:
    """List recent completed outcomes."""
    data = api_get("/api/outcomes", limit=limit)

    if as_json:
        format_result(data, as_json=True)
        return

    outcomes = data if isinstance(data, list) else data.get("outcomes", [])
    if not outcomes:
        click.echo("No outcomes recorded yet.")
        return

    rows = []
    for o in outcomes:
        thread_id = o.get("thread_id", "-")
        outcome_type = o.get("outcome_type", "-")
        summary = (o.get("summary") or "")[:60]
        created = (o.get("created_at") or "")[:10]
        rows.append([f"#{thread_id}", outcome_type, summary, created])

    format_table(["Thread", "Type", "Summary", "Date"], rows)


@outcomes_group.command("get")
@click.argument("thread_id", type=int)
@json_option
def get_outcome(thread_id: int, as_json: bool) -> None:
    """Get the outcome for a specific thread."""
    data = api_get(f"/api/outcomes/{thread_id}")

    if as_json:
        format_result(data, as_json=True)
        return

    if not data:
        click.echo(f"No outcome found for thread #{thread_id}.")
        return

    click.echo(f"Thread:  #{data.get('thread_id', thread_id)}")
    click.echo(f"Type:    {data.get('outcome_type', '-')}")
    click.echo(f"Summary: {data.get('summary', '-')}")
    click.echo(f"Date:    {(data.get('created_at') or '')[:10]}")

    details = data.get("details")
    if details and isinstance(details, dict):
        click.echo("Details:")
        for key, value in details.items():
            click.echo(f"  {key}: {value}")

    outcome_file = data.get("outcome_file")
    if outcome_file:
        click.echo(f"File:    {outcome_file}")


@outcomes_group.command("extract")
@click.argument("thread_id", type=int)
@json_option
def extract_outcome(thread_id: int, as_json: bool) -> None:
    """Trigger knowledge extraction for a completed thread."""
    data = api_post(f"/api/threads/{thread_id}/extract")

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Outcome extracted for thread #{thread_id}")
    if data:
        click.echo(f"  Type:    {data.get('outcome_type', '-')}")
        click.echo(f"  Summary: {data.get('summary', '-')}")
