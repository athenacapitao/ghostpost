"""Shared HTTP client for CLI commands — authenticates via X-API-Key."""

import json
import sys

import click
import httpx

from src.api.auth import create_access_token
from src.config import settings

DEFAULT_URL = "http://127.0.0.1:8000"

# Module-level flag: when True, errors are emitted as JSON instead of human text.
_json_mode: bool = False


def set_json_mode(enabled: bool) -> None:
    """Enable or disable JSON mode for structured error output."""
    global _json_mode
    _json_mode = enabled


def _handle_connect_error() -> None:
    """Emit a structured or human-readable connection error and exit."""
    if _json_mode:
        click.echo(
            json.dumps(
                {
                    "ok": False,
                    "error": "Connection refused",
                    "code": "CONNECTION_ERROR",
                    "retryable": True,
                }
            )
        )
    else:
        click.echo("Error: Could not connect to GhostPost API", err=True)
    sys.exit(1)


def _handle_http_error(exc: httpx.HTTPStatusError) -> None:
    """Emit a structured or human-readable HTTP error and exit."""
    status = exc.response.status_code
    if _json_mode:
        code = "HTTP_5XX" if status >= 500 else "HTTP_4XX"
        retryable = status >= 500 or status == 429
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        click.echo(
            json.dumps(
                {
                    "ok": False,
                    "error": str(detail),
                    "code": code,
                    "retryable": retryable,
                    "status": status,
                }
            )
        )
    else:
        click.echo(f"Error: {status} — {exc.response.text}", err=True)
    sys.exit(1)


def get_api_client(base_url: str = DEFAULT_URL) -> httpx.Client:
    """Create an authenticated httpx client using a JWT token."""
    token = create_access_token(subject=settings.ADMIN_USERNAME)
    return httpx.Client(
        base_url=base_url,
        headers={"X-API-Key": token},
        timeout=30,
    )


def api_get(path: str, base_url: str = DEFAULT_URL, **params) -> dict:
    """Make an authenticated GET request."""
    try:
        client = get_api_client(base_url)
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        _handle_connect_error()
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)


def api_post(path: str, base_url: str = DEFAULT_URL, **kwargs) -> dict:
    """Make an authenticated POST request."""
    try:
        client = get_api_client(base_url)
        response = client.post(path, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        _handle_connect_error()
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)


def api_put(path: str, base_url: str = DEFAULT_URL, **kwargs) -> dict:
    """Make an authenticated PUT request."""
    try:
        client = get_api_client(base_url)
        response = client.put(path, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        _handle_connect_error()
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)


def api_delete(path: str, base_url: str = DEFAULT_URL, **kwargs) -> dict:
    """Make an authenticated DELETE request."""
    try:
        client = get_api_client(base_url)
        response = client.delete(path, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        _handle_connect_error()
    except httpx.HTTPStatusError as e:
        _handle_http_error(e)
