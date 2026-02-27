"""CLI commands for contacts — list and detail."""

import click

from src.cli.api_client import api_get
from src.cli.formatters import format_result, format_table, json_option


@click.command("contacts")
@click.option("--limit", default=20, type=int, help="Max contacts to show")
@click.option("--search", "query", default=None, help="Search by name or email")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def contacts_cmd(limit: int, query: str | None, url: str, as_json: bool) -> None:
    """List contacts."""
    params = {"page_size": limit}
    if query:
        params["q"] = query
    data = api_get("/api/contacts", url, **params)

    if as_json:
        format_result(data, as_json=True)
        return

    items = data.get("items", [])
    if not items:
        click.echo("No contacts found.")
        return

    rows = []
    for c in items:
        rows.append([
            c["id"],
            (c.get("name") or "")[:25],
            (c.get("email") or "")[:30],
            (c.get("company") or "-")[:20],
            (c.get("last_interaction") or "")[:10],
        ])
    format_table(["ID", "Name", "Email", "Company", "Last Seen"], rows)
    click.echo(f"\n{data.get('total', len(items))} total contacts")


@click.command("contact")
@click.argument("contact_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def contact_cmd(contact_id: int, url: str, as_json: bool) -> None:
    """Show contact details."""
    data = api_get(f"/api/contacts/{contact_id}", url)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Contact #{data.get('id', contact_id)}")
    click.echo(f"  Name:    {data.get('name', '-')}")
    click.echo(f"  Email:   {data.get('email', '-')}")
    if data.get("company"):
        click.echo(f"  Company: {data['company']}")
    if data.get("title"):
        click.echo(f"  Title:   {data['title']}")
    if data.get("relationship_type"):
        click.echo(f"  Type:    {data['relationship_type']}")
    if data.get("topics"):
        click.echo(f"  Topics:  {data['topics']}")
    if data.get("last_interaction"):
        click.echo(f"  Last:    {str(data['last_interaction'])[:16]}")
    if data.get("notes"):
        click.echo(f"  Notes:   {data['notes']}")
