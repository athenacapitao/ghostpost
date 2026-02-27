"""Playbook CLI commands."""

import click

from src.cli.api_client import api_delete, api_get, api_post, api_put, get_api_client
from src.cli.formatters import format_result, json_option


@click.command("playbooks")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def playbooks_cmd(url: str, as_json: bool) -> None:
    """List all available playbooks."""
    items = api_get("/api/playbooks", url)

    if as_json:
        format_result(items, as_json=True)
        return

    if not items:
        click.echo("No playbooks found.")
        return
    for item in items:
        click.echo(f"  {item['name']:<25} {item['title']}")


@click.command("playbook")
@click.argument("name")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def playbook_cmd(name: str, url: str, as_json: bool) -> None:
    """Show the full content of a playbook."""
    client = get_api_client(url)
    response = client.get(f"/api/playbooks/{name}")
    if response.status_code == 404:
        click.echo(f"Error: Playbook '{name}' not found", err=True)
        raise SystemExit(1)
    response.raise_for_status()

    if as_json:
        format_result({"name": name, "content": response.text}, as_json=True)
        return

    click.echo(response.text)


@click.command("apply-playbook")
@click.argument("thread_id", type=int)
@click.argument("name")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def apply_playbook_cmd(thread_id: int, name: str, url: str, as_json: bool) -> None:
    """Apply a playbook to a thread."""
    client = get_api_client(url)
    response = client.post(f"/api/playbooks/apply/{thread_id}/{name}")
    if response.status_code == 404:
        click.echo(f"Error: {response.json().get('detail', 'Not found')}", err=True)
        raise SystemExit(1)
    response.raise_for_status()
    data = response.json()

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(data["message"])


@click.command("playbook-create")
@click.argument("name")
@click.option("--body", prompt="Playbook content (markdown)", help="Markdown content")
@json_option
def playbook_create_cmd(name: str, body: str, as_json: bool) -> None:
    """Create a new playbook."""
    data = api_post("/api/playbooks", json={"content": body}, params={"name": name})

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Created playbook: {data['name']} — {data['title']}")


@click.command("playbook-update")
@click.argument("name")
@click.option("--body", prompt="Updated playbook content (markdown)", help="New markdown content")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def playbook_update_cmd(name: str, body: str, url: str, as_json: bool) -> None:
    """Update an existing playbook's content."""
    data = api_put(f"/api/playbooks/{name}", url, json={"content": body})

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Updated playbook: {data.get('name', name)}")


@click.command("playbook-delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this playbook?")
@json_option
def playbook_delete_cmd(name: str, as_json: bool) -> None:
    """Delete a playbook by name."""
    data = api_delete(f"/api/playbooks/{name}")

    if as_json:
        format_result(data if data else {"deleted": name}, as_json=True)
        return

    click.echo(f"Deleted playbook: {name}")
