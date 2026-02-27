"""CLI commands for attachments — download."""

import os

import click

from src.cli.api_client import get_api_client
from src.cli.formatters import format_result, json_option

MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50 MB


def _safe_filename(name: str, fallback: str) -> str:
    """Sanitize filename — strip path components to prevent traversal."""
    name = os.path.basename(name)
    name = name.replace("\x00", "").strip(". ")
    return name if name else fallback


@click.command("attachment")
@click.argument("attachment_id", type=int)
@click.option("--output", "-o", default=None, help="Output file path (default: ./attachments/<filename>)")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@json_option
def attachment_cmd(attachment_id: int, output: str | None, url: str, as_json: bool) -> None:
    """Download an attachment by ID."""
    client = get_api_client(url)
    try:
        response = client.get(f"/api/attachments/{attachment_id}/download")
        response.raise_for_status()
    except Exception as e:
        if as_json:
            import json
            click.echo(json.dumps({
                "ok": False,
                "error": str(e),
                "code": "DOWNLOAD_ERROR",
                "retryable": False,
            }))
        else:
            click.echo(f"Error downloading attachment: {e}", err=True)
        raise SystemExit(1)

    # Size check
    if len(response.content) > MAX_ATTACHMENT_SIZE:
        msg = f"Attachment too large: {len(response.content)} bytes (max {MAX_ATTACHMENT_SIZE})"
        if as_json:
            import json
            click.echo(json.dumps({"ok": False, "error": msg, "code": "TOO_LARGE", "retryable": False}))
        else:
            click.echo(f"Error: {msg}", err=True)
        raise SystemExit(1)

    # Determine filename from Content-Disposition or fallback
    cd = response.headers.get("content-disposition", "")
    fallback = f"attachment_{attachment_id}"
    filename = fallback
    if "filename=" in cd:
        raw = cd.split("filename=")[-1].strip('"').strip("'")
        filename = _safe_filename(raw, fallback)

    # Determine output path
    if output:
        save_path = output
    else:
        save_dir = os.path.join(os.getcwd(), "attachments")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

    # Final path containment check (when not using explicit --output)
    if not output:
        real_save = os.path.realpath(save_path)
        real_dir = os.path.realpath(save_dir)
        if not real_save.startswith(real_dir + os.sep) and real_save != real_dir:
            msg = f"Unsafe filename rejected: {filename}"
            if as_json:
                import json
                click.echo(json.dumps({"ok": False, "error": msg, "code": "UNSAFE_FILENAME", "retryable": False}))
            else:
                click.echo(f"Error: {msg}", err=True)
            raise SystemExit(1)

    with open(save_path, "wb") as f:
        f.write(response.content)

    size = len(response.content)

    if as_json:
        format_result({"path": save_path, "filename": filename, "size": size}, as_json=True)
        return

    click.echo(f"Saved: {filename} ({size} bytes) → {save_path}")
