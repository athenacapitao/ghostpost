"""CLI commands for email actions — reply, draft, compose."""

import click

from src.cli.api_client import api_get, api_post, api_put
from src.cli.formatters import format_result, json_option


@click.command("reply")
@click.argument("thread_id", type=int)
@click.option("--body", "-b", required=True, help="Reply body text")
@click.option("--cc", help="CC addresses (comma-separated)")
@click.option("--draft", is_flag=True, default=False, help="Save as draft instead of sending")
@json_option
def reply_cmd(thread_id: int, body: str, cc: str | None, draft: bool, as_json: bool) -> None:
    """Send a reply to a thread, or save it as a draft with --draft."""
    payload = {"body": body}
    if cc:
        payload["cc"] = [addr.strip() for addr in cc.split(",")]
    params = {"draft": "true"} if draft else {}
    data = api_post(f"/api/threads/{thread_id}/reply", json=payload, params=params)

    if as_json:
        format_result(data, as_json=True)
        return

    if draft:
        click.echo(f"Draft created! ID: {data.get('draft_id', 'unknown')}")
    else:
        click.echo(f"Reply sent! Gmail ID: {data.get('gmail_id', 'unknown')}")
        warnings = data.get("warnings", [])
        for w in warnings:
            click.echo(f"  Warning: {w}")


@click.command("draft")
@click.argument("thread_id", type=int)
@click.option("--to", required=True, help="Recipient email")
@click.option("--subject", "-s", required=True, help="Subject line")
@click.option("--body", "-b", required=True, help="Draft body text")
@json_option
def draft_cmd(thread_id: int, to: str, subject: str, body: str, as_json: bool) -> None:
    """Create a draft for a thread."""
    payload = {"to": to, "subject": subject, "body": body}
    data = api_post(f"/api/threads/{thread_id}/draft", json=payload)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Draft created! ID: {data.get('draft_id')}")


@click.command("compose")
@click.option("--to", required=True, help="Recipient email")
@click.option("--subject", "-s", required=True, help="Subject line")
@click.option("--body", "-b", required=True, help="Email body text")
@click.option("--cc", help="CC addresses (comma-separated)")
@click.option("--goal", help="Thread goal for the AI agent")
@click.option("--acceptance-criteria", help="Goal acceptance criteria")
@click.option("--playbook", help="Playbook to follow (e.g. sales, support)")
@click.option("--auto-reply", type=click.Choice(["off", "draft", "auto"]), help="Auto-reply mode")
@click.option("--follow-up-days", type=int, help="Days before follow-up")
@click.option("--priority", type=click.Choice(["low", "medium", "high", "critical"]), help="Thread priority")
@click.option("--category", help="Initial category")
@click.option("--notes", help="Notes for the AI agent")
@json_option
def compose_cmd(
    to: str,
    subject: str,
    body: str,
    cc: str | None,
    goal: str | None,
    acceptance_criteria: str | None,
    playbook: str | None,
    auto_reply: str | None,
    follow_up_days: int | None,
    priority: str | None,
    category: str | None,
    notes: str | None,
    as_json: bool,
) -> None:
    """Compose and send a new email."""
    payload: dict = {"to": to, "subject": subject, "body": body}
    if cc:
        payload["cc"] = [addr.strip() for addr in cc.split(",")]
    # Agent context — only include fields that were explicitly provided.
    if goal:
        payload["goal"] = goal
    if acceptance_criteria:
        payload["acceptance_criteria"] = acceptance_criteria
    if playbook:
        payload["playbook"] = playbook
    if auto_reply:
        payload["auto_reply_mode"] = auto_reply
    if follow_up_days is not None:
        payload["follow_up_days"] = follow_up_days
    if priority:
        payload["priority"] = priority
    if category:
        payload["category"] = category
    if notes:
        payload["notes"] = notes

    data = api_post("/api/compose", json=payload)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Email sent! Gmail ID: {data.get('gmail_id', 'unknown')}")
    if data.get("thread_id"):
        click.echo(f"Thread ID: {data['thread_id']}")
    for w in data.get("warnings", []):
        click.echo(f"  Warning: {w}")
    if data.get("brief"):
        click.echo("")
        click.echo(data["brief"])


@click.command("drafts")
@click.option("--status", default="pending", help="Filter by status")
@json_option
def drafts_cmd(status: str, as_json: bool) -> None:
    """List drafts."""
    data = api_get("/api/drafts", status=status)

    if as_json:
        format_result(data, as_json=True)
        return

    if not data:
        click.echo("No drafts found.")
        return
    for d in data:
        to = ", ".join(d.get("to_addresses") or []) if isinstance(d.get("to_addresses"), list) else "unknown"
        click.echo(f"  #{d['id']}  [{d['status']}]  To: {to}  Subject: {d.get('subject', '(none)')}")


@click.command("draft-approve")
@click.argument("draft_id", type=int)
@json_option
def draft_approve_cmd(draft_id: int, as_json: bool) -> None:
    """Approve and send a draft."""
    data = api_post(f"/api/drafts/{draft_id}/approve")

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(data.get("message", "Done"))


@click.command("draft-reject")
@click.argument("draft_id", type=int)
@json_option
def draft_reject_cmd(draft_id: int, as_json: bool) -> None:
    """Reject a draft."""
    data = api_post(f"/api/drafts/{draft_id}/reject")

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(data.get("message", "Done"))


@click.command("toggle")
@click.argument("thread_id", type=int)
@click.option("--mode", required=True, type=click.Choice(["off", "draft", "auto"]), help="Auto-reply mode")
@json_option
def toggle_cmd(thread_id: int, mode: str, as_json: bool) -> None:
    """Toggle auto-reply mode for a thread."""
    data = api_put(f"/api/threads/{thread_id}/auto-reply", json={"mode": mode})

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Auto-reply mode set to: {data.get('auto_reply_mode', mode)}")


@click.command("followup")
@click.argument("thread_id", type=int)
@click.option("--days", required=True, type=int, help="Follow-up period in days")
@json_option
def followup_cmd(thread_id: int, days: int, as_json: bool) -> None:
    """Set follow-up days for a thread."""
    data = api_put(f"/api/threads/{thread_id}/follow-up", json={"days": days})

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"Follow-up set to {data.get('follow_up_days', days)} days")


@click.command("state")
@click.argument("thread_id", type=int)
@click.argument("new_state")
@click.option("--reason", help="Reason for state change")
@json_option
def state_cmd(thread_id: int, new_state: str, reason: str | None, as_json: bool) -> None:
    """Change thread state."""
    payload = {"state": new_state.upper()}
    if reason:
        payload["reason"] = reason
    data = api_put(f"/api/threads/{thread_id}/state", json=payload)

    if as_json:
        format_result(data, as_json=True)
        return

    click.echo(f"State changed: {data.get('old_state')} -> {data.get('new_state')}")


@click.command("generate-reply")
@click.argument("thread_id", type=int)
@click.option("--instructions", "-i", help="Specific instructions for this reply")
@click.option(
    "--style",
    "-s",
    type=click.Choice(["professional", "casual", "formal", "custom"]),
    help="Override reply style for this reply",
)
@click.option("--draft", "create_draft", is_flag=True, default=False, help="Auto-create a draft from the generated reply")
@json_option
def generate_reply_cmd(
    thread_id: int,
    instructions: str | None,
    style: str | None,
    create_draft: bool,
    as_json: bool,
) -> None:
    """Generate a reply using AI."""
    params: dict = {}
    if instructions:
        params["instructions"] = instructions
    if style:
        params["style"] = style
    if create_draft:
        params["create_draft"] = "true"
    result = api_post(f"/api/threads/{thread_id}/generate-reply", params=params)

    if as_json:
        format_result(result, as_json=True)
        return

    if "error" in result:
        click.echo(f"Error: {result['error']}")
    else:
        click.echo(f"To: {result.get('to', '')}")
        click.echo(f"Subject: {result.get('subject', '')}")
        click.echo(f"Style: {result.get('style', '')}")
        if result.get("draft_id"):
            click.echo(f"Draft ID: {result['draft_id']}")
        click.echo(f"\n{result.get('body', '')}")
