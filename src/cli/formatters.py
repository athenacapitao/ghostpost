"""CLI output formatters — JSON (default) and table."""

import functools
import json

import click


def format_json(data) -> None:
    """Pretty-print as JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


def format_result(data, as_json: bool = False) -> None:
    """Output data in agent-friendly JSON envelope or raw JSON format.

    When as_json is True the output is wrapped in {"ok": true, "data": ...}
    so that the calling agent can reliably parse success vs failure.
    When as_json is False the raw data is pretty-printed (existing behaviour).
    """
    if as_json:
        click.echo(json.dumps({"ok": True, "data": data}, indent=2, default=str))
    else:
        format_json(data)


def format_table(headers: list[str], rows: list[list]) -> None:
    """Simple table output."""
    if not rows:
        click.echo("No results.")
        return

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Print header
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    click.echo(header_line)
    click.echo("  ".join("-" * w for w in widths))

    # Print rows
    for row in rows:
        line = "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
        click.echo(line)


def json_option(f):
    """Decorator that adds a --json flag to a Click command.

    The decorated function receives an extra ``as_json`` keyword argument.
    When the flag is passed, json_mode is enabled in api_client so that
    HTTP / connection errors are also emitted as structured JSON.
    """
    @click.option(
        "--json",
        "as_json",
        is_flag=True,
        default=False,
        help="Output structured JSON for agent consumption.",
    )
    @functools.wraps(f)
    def wrapper(*args, as_json: bool = False, **kwargs):
        if as_json:
            from src.cli.api_client import set_json_mode
            set_json_mode(True)
        return f(*args, as_json=as_json, **kwargs)

    return wrapper
