"""Enrichment CLI commands."""

import click

from src.cli.api_client import api_get, api_post
from src.cli.formatters import format_result, json_option


@click.command("enrich")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def enrich_cmd(url, as_json):
    """Trigger AI enrichment (categorize, summarize, analyze)."""
    data = api_post("/api/enrich", url)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(data["message"])
    if not data.get("llm_available"):
        click.echo("Note: LLM not configured — only rule-based enrichment will run")
        click.echo("Set LLM_GATEWAY_TOKEN in .env to enable AI features via OpenClaw")


@click.command("brief")
@click.argument("thread_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def brief_cmd(thread_id, url, as_json):
    """Show structured brief for a thread."""
    from src.cli.api_client import get_api_client
    client = get_api_client(url)
    response = client.get(f"/api/threads/{thread_id}/brief")
    response.raise_for_status()

    if as_json:
        # The brief endpoint returns markdown text; wrap it in the envelope.
        format_result({"thread_id": thread_id, "brief": response.text}, as_json=True)
        return

    click.echo(response.text)


@click.command("enrich-web")
@click.argument("contact_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def enrich_web_cmd(contact_id, url, as_json):
    """Enrich a contact using web/domain knowledge (LLM inference from name + email domain)."""
    data = api_post(f"/api/contacts/{contact_id}/enrich-web", url)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Web enrichment result for contact {contact_id}:")
    for key, value in data.items():
        if value is not None:
            click.echo(f"  {key}: {value}")
