"""CLI commands for settings management."""

import click

from src.cli.api_client import api_delete, api_get, api_put
from src.cli.formatters import format_result, json_option


@click.command("settings")
@click.argument("action", type=click.Choice(["list", "get", "set", "delete", "bulk"]))
@click.argument("args", nargs=-1)
@json_option
def settings_cmd(action: str, args: tuple, as_json: bool) -> None:
    """Manage GhostPost settings.

    \b
    Usage:
      settings list                          List all settings
      settings get <key>                     Get a setting value
      settings set <key> <value>             Set a setting value
      settings delete <key>                  Delete/reset a setting
      settings bulk <key=val> [key=val] ...  Update multiple settings
    """
    if action == "list":
        data = api_get("/api/settings")
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo("Settings:")
            for k, v in sorted(data.items()):
                click.echo(f"  {k}: {v}")
    elif action == "get":
        if not args:
            click.echo("Error: key required for 'get'", err=True)
            raise SystemExit(1)
        key = args[0]
        data = api_get(f"/api/settings/{key}")
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(f"{data['key']}: {data['value']}")
    elif action == "set":
        if len(args) < 2:
            click.echo("Error: key and value required for 'set'", err=True)
            raise SystemExit(1)
        key, value = args[0], args[1]
        data = api_put(f"/api/settings/{key}", json={"value": value})
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(f"Set {data['key']} = {data['value']}")
    elif action == "delete":
        if not args:
            click.echo("Error: key required for 'delete'", err=True)
            raise SystemExit(1)
        key = args[0]
        data = api_delete(f"/api/settings/{key}")
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(data.get("message", f"Deleted setting: {key}"))
    elif action == "bulk":
        if not args:
            click.echo("Error: at least one key=value pair required for 'bulk'", err=True)
            raise SystemExit(1)
        settings_dict = {}
        for pair in args:
            if "=" not in pair:
                click.echo(f"Error: invalid format '{pair}' — expected key=value", err=True)
                raise SystemExit(1)
            k, v = pair.split("=", 1)
            settings_dict[k] = v
        data = api_put("/api/settings/bulk", json={"settings": settings_dict})
        if as_json:
            format_result(data, as_json=True)
        else:
            updated = data.get("updated", list(settings_dict.keys()))
            click.echo(f"Updated {len(updated)} settings: {', '.join(updated)}")
