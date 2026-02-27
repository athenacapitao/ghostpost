import json

import click
import httpx


@click.group()
@click.version_option(version="0.1.0", prog_name="ghostpost")
def cli() -> None:
    """GhostPost - Agent-first email management system."""
    pass


@cli.command()
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output for agent consumption.")
def health(url: str, as_json: bool) -> None:
    """Check GhostPost API health."""
    try:
        response = httpx.get(f"{url}/api/health", timeout=5)
        data = response.json()
        if as_json:
            click.echo(json.dumps({"ok": data.get("status") == "ok", "data": data}, indent=2, default=str))
        else:
            click.echo(f"Status: {data['status']}")
            click.echo(f"  DB:    {'OK' if data['db'] else 'FAIL'}")
            click.echo(f"  Redis: {'OK' if data['redis'] else 'FAIL'}")
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


# Register subcommands
from src.cli.threads import threads_cmd, thread_cmd, notes_cmd  # noqa: E402
from src.cli.emails import email_cmd, search_cmd  # noqa: E402
from src.cli.system import sync_cmd, stats_cmd, status_cmd  # noqa: E402
from src.cli.enrich import enrich_cmd, brief_cmd, enrich_web_cmd  # noqa: E402
from src.cli.playbooks import playbooks_cmd, playbook_cmd, apply_playbook_cmd, playbook_create_cmd, playbook_delete_cmd, playbook_update_cmd  # noqa: E402
from src.cli.actions import (  # noqa: E402
    reply_cmd, draft_cmd, compose_cmd, drafts_cmd,
    draft_approve_cmd, draft_reject_cmd,
    toggle_cmd, followup_cmd, state_cmd,
    generate_reply_cmd,
)
from src.cli.goals import goal_cmd  # noqa: E402
from src.cli.security import quarantine_cmd, blocklist_cmd, audit_cmd, security_events_cmd  # noqa: E402
from src.cli.settings import settings_cmd  # noqa: E402
from src.cli.research import research_group  # noqa: E402
from src.cli.triage import triage_cmd  # noqa: E402
from src.cli.outcomes import outcomes_group  # noqa: E402
from src.cli.contacts import contacts_cmd, contact_cmd  # noqa: E402
from src.cli.notifications import alerts_cmd  # noqa: E402
from src.cli.attachments import attachment_cmd  # noqa: E402
from src.cli.batch import batch_group  # noqa: E402

cli.add_command(threads_cmd)
cli.add_command(thread_cmd)
cli.add_command(email_cmd)
cli.add_command(search_cmd)
cli.add_command(sync_cmd)
cli.add_command(stats_cmd)
cli.add_command(status_cmd)
cli.add_command(enrich_cmd)
cli.add_command(brief_cmd)
cli.add_command(enrich_web_cmd)
cli.add_command(playbooks_cmd)
cli.add_command(playbook_cmd)
cli.add_command(apply_playbook_cmd)
cli.add_command(playbook_create_cmd)
cli.add_command(playbook_delete_cmd)
cli.add_command(reply_cmd)
cli.add_command(draft_cmd)
cli.add_command(compose_cmd)
cli.add_command(drafts_cmd)
cli.add_command(draft_approve_cmd)
cli.add_command(draft_reject_cmd)
cli.add_command(toggle_cmd)
cli.add_command(followup_cmd)
cli.add_command(state_cmd)
cli.add_command(generate_reply_cmd)
cli.add_command(goal_cmd)
cli.add_command(quarantine_cmd)
cli.add_command(blocklist_cmd)
cli.add_command(audit_cmd)
cli.add_command(settings_cmd)
cli.add_command(research_group)
cli.add_command(triage_cmd)
cli.add_command(outcomes_group)
cli.add_command(contacts_cmd)
cli.add_command(contact_cmd)
cli.add_command(notes_cmd)
cli.add_command(alerts_cmd)
cli.add_command(security_events_cmd)
cli.add_command(attachment_cmd)
cli.add_command(batch_group)
cli.add_command(playbook_update_cmd)
