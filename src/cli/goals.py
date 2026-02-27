"""CLI commands for goal management."""

import click

from src.cli.api_client import api_delete, api_get, api_post, api_put
from src.cli.formatters import format_result, json_option


@click.command("goal")
@click.argument("thread_id", type=int)
@click.option("--set", "goal_text", help="Set a goal for the thread")
@click.option("--criteria", help="Acceptance criteria")
@click.option("--status", type=click.Choice(["in_progress", "met", "abandoned"]), help="Update goal status")
@click.option("--check", is_flag=True, help="Use LLM to check if goal is met")
@click.option("--clear", is_flag=True, help="Clear the goal")
@json_option
def goal_cmd(
    thread_id: int,
    goal_text: str | None,
    criteria: str | None,
    status: str | None,
    check: bool,
    clear: bool,
    as_json: bool,
) -> None:
    """Manage thread goals."""
    if goal_text:
        payload = {"goal": goal_text}
        if criteria:
            payload["acceptance_criteria"] = criteria
        data = api_put(f"/api/threads/{thread_id}/goal", json=payload)
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(f"Goal set: {data.get('goal', goal_text)}")
    elif status:
        data = api_put(f"/api/threads/{thread_id}/goal/status", json={"status": status})
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(f"Goal status: {data.get('goal_status', status)}")
    elif check:
        data = api_post(f"/api/threads/{thread_id}/goal/check")
        if as_json:
            format_result(data, as_json=True)
        else:
            met = data.get("met", False)
            reason = data.get("reason", "Unknown")
            click.echo(f"Goal met: {'Yes' if met else 'No'}")
            click.echo(f"Reason: {reason}")
    elif clear:
        data = api_delete(f"/api/threads/{thread_id}/goal")
        if as_json:
            format_result(data, as_json=True)
        else:
            click.echo(data.get("message", "Goal cleared"))
    else:
        # Show current goal
        data = api_get(f"/api/threads/{thread_id}")
        goal = data.get("goal")
        if as_json:
            goal_data = {
                "goal": goal,
                "acceptance_criteria": data.get("acceptance_criteria"),
                "goal_status": data.get("goal_status"),
            }
            format_result(goal_data, as_json=True)
        elif goal:
            click.echo(f"Goal: {goal}")
            click.echo(f"Criteria: {data.get('acceptance_criteria', 'None')}")
            click.echo(f"Status: {data.get('goal_status', 'unknown')}")
        else:
            click.echo("No goal set for this thread.")
