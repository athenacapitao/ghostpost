"""CLI commands for notifications — alerts."""

import click

from src.cli.api_client import api_get
from src.cli.formatters import format_result, json_option


@click.command("alerts")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def alerts_cmd(url: str, as_json: bool) -> None:
    """Show active notification alerts."""
    data = api_get("/api/notifications/alerts", url)

    if as_json:
        format_result(data, as_json=True)
        return

    alerts = data.get("alerts", [])
    if not alerts:
        click.echo("No active alerts.")
        return

    click.echo(f"{data.get('count', len(alerts))} active alert(s):")
    for alert in alerts:
        click.echo(f"  - {alert}")
