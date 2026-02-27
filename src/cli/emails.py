"""Email CLI commands."""

import click

from src.cli.api_client import api_get
from src.cli.formatters import format_json, format_result, format_table, json_option


@click.command("email")
@click.argument("email_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def email_cmd(email_id, url, as_json):
    """Show a single email."""
    data = api_get(f"/api/emails/{email_id}", url)
    format_result(data, as_json=as_json)


@click.command("search")
@click.argument("query")
@click.option("--limit", default=10, help="Number of results")
@click.option("--table", "as_table", is_flag=True, help="Table output")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def search_cmd(query, limit, as_table, url, as_json):
    """Search emails by subject, body, or sender."""
    data = api_get("/api/emails/search", url, q=query, page_size=limit)

    if as_json:
        format_result(data, as_json=True)
    elif as_table:
        headers = ["ID", "From", "Subject", "Date"]
        rows = [
            [
                e["id"],
                (e["from_address"] or "")[:30],
                (e["subject"] or "")[:40],
                (e["date"] or "")[:16],
            ]
            for e in data["items"]
        ]
        format_table(headers, rows)
        click.echo(f"\n{data['total']} results")
    else:
        format_json(data)
