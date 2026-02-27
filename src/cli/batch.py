"""CLI commands for enrichment batch job management."""

import click

from src.cli.api_client import api_get, api_post
from src.cli.formatters import format_result, format_table, json_option


@click.group("batch")
def batch_group() -> None:
    """Manage enrichment batch jobs."""
    pass


@batch_group.command("list")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def batch_list(url: str, as_json: bool) -> None:
    """List all batch jobs."""
    data = api_get("/api/batch", url)

    if as_json:
        format_result(data, as_json=True)
        return

    if not data:
        click.echo("No batch jobs found.")
        return

    rows = []
    for job in data:
        rows.append([
            job.get("id", "-"),
            (job.get("job_type") or "-")[:15],
            job.get("status", "-"),
            job.get("total_items", 0),
            job.get("completed_items", 0),
            (job.get("created_at") or "")[:16],
        ])
    format_table(["ID", "Type", "Status", "Total", "Done", "Created"], rows)


@batch_group.command("detail")
@click.argument("batch_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def batch_detail(batch_id: int, url: str, as_json: bool) -> None:
    """Show batch job details."""
    data = api_get(f"/api/batch/{batch_id}", url)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Batch #{data.get('id', batch_id)}")
    click.echo(f"  Type:      {data.get('job_type', '-')}")
    click.echo(f"  Status:    {data.get('status', '-')}")
    click.echo(f"  Progress:  {data.get('completed_items', 0)}/{data.get('total_items', 0)}")
    if data.get("error"):
        click.echo(f"  Error:     {data['error']}")
    click.echo(f"  Created:   {(data.get('created_at') or '')[:16]}")


@batch_group.command("cancel")
@click.argument("batch_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def batch_cancel(batch_id: int, url: str, as_json: bool) -> None:
    """Cancel a running batch job."""
    data = api_post(f"/api/batch/{batch_id}/cancel", url)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Batch #{batch_id} cancelled.")
