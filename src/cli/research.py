"""Ghost Research CLI commands."""

import json
import os
import time

import click
import httpx


def _get_headers(url: str) -> dict:
    """Get auth headers for API requests."""
    token = os.environ.get("GHOSTPOST_TOKEN", "")
    if not token:
        try:
            resp = httpx.post(
                f"{url}/api/auth/login",
                json={"password": os.environ.get("GHOSTPOST_PASSWORD", "ghostpost")},
                timeout=5,
            )
            if resp.status_code == 200:
                token = resp.json().get("token", "")
        except Exception:
            pass
    return {"X-API-Key": token} if token else {}


def _output(data, as_json: bool, message: str = "") -> None:
    """Output data in JSON or human-readable format."""
    if as_json:
        click.echo(json.dumps({"ok": True, "data": data}, indent=2, default=str))
    elif message:
        click.echo(message)


PHASE_LABELS = {
    1: "Input Collection",
    2: "Deep Research",
    3: "Opportunity Analysis",
    4: "Contacts Search",
    5: "Person Research",
    6: "Peer Intelligence",
    7: "Value Proposition",
    8: "Email Composition",
}

MAX_PHASES = 8


def _watch_campaign(campaign_id: int, url: str, headers: dict) -> None:
    """Poll campaign status until completion, streaming verbose log entries in real time."""
    last_log_idx = 0
    last_phase = 0
    spinner_chars = "|/-\\"
    tick = 0

    while True:
        try:
            resp = httpx.get(f"{url}/api/research/{campaign_id}", headers=headers, timeout=10)
            if resp.status_code != 200:
                click.echo(f"\n  Error polling status: HTTP {resp.status_code}", err=True)
                break

            data = resp.json()
            status = data.get("status", "")
            phase = data.get("phase", 0)
            error = data.get("error")
            research_data = data.get("research_data") or {}

            # Print new verbose log entries
            verbose_log = research_data.get("verbose_log", [])
            if len(verbose_log) > last_log_idx:
                for entry in verbose_log[last_log_idx:]:
                    ts = entry.get("ts", "")
                    p = entry.get("phase", 0)
                    msg = entry.get("msg", "")
                    phase_tag = f"P{p}" if p > 0 else "--"
                    click.echo(f"  [{ts}] [{phase_tag}] {msg}")
                last_log_idx = len(verbose_log)

            # Track phase changes (for spinner between log entries)
            if phase != last_phase and phase > 0:
                last_phase = phase

            # Terminal states
            if status in ("sent", "draft_pending", "completed"):
                click.echo(f"  Pipeline finished: {status}")
                if data.get("email_subject"):
                    click.echo(f"  Email subject: {data['email_subject']}")
                if data.get("thread_id"):
                    click.echo(f"  Thread: #{data['thread_id']}")
                break

            if status == "failed":
                click.echo(f"  FAILED: {error or 'unknown'}", err=True)
                break

            # Spinner between polls when no new log entries
            if last_phase > 0 and len(verbose_log) == last_log_idx:
                s = spinner_chars[tick % 4]
                label = PHASE_LABELS.get(phase, f"Phase {phase}")
                click.echo(f"\r  [{phase}/{MAX_PHASES}] {label}... {s}  ", nl=False)

            tick += 1

        except Exception as e:
            click.echo(f"\n  Connection error: {e}", err=True)

        time.sleep(2)


@click.group("research")
def research_group() -> None:
    """Ghost Research — company research and outreach pipeline."""
    pass


@research_group.command("run")
@click.argument("company")
@click.option("--goal", required=True, help="Primary goal for the outreach")
@click.option("--identity", default="default", help="Sender identity to use")
@click.option("--language", default="pt-PT", help="Email language (pt-PT, en, es, fr, auto)")
@click.option("--country", default=None, help="Target company country")
@click.option("--industry", default=None, help="Target company industry")
@click.option("--contact-name", default=None, help="Contact person name")
@click.option("--contact-email", default=None, help="Contact email address")
@click.option("--contact-role", default=None, help="Contact role/title")
@click.option("--cc", default=None, help="CC recipients (comma-separated emails)")
@click.option("--extra-context", default=None, help="Extra context for the research pipeline")
@click.option("--tone", default="direct-value", help="Email tone (direct-value, consultative, relationship-first, challenger-sale)")
@click.option("--mode", default="draft-for-approval", help="Auto-reply mode (draft-for-approval, autonomous, notify-only)")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.option("--watch/--no-watch", "watch", default=True, help="Watch progress with verbose output (default: on)")
def research_run(company, goal, identity, language, country, industry,
                 contact_name, contact_email, contact_role, cc, extra_context,
                 tone, mode, url, as_json, watch) -> None:
    """Start research pipeline for a single company."""
    headers = _get_headers(url)
    payload = {
        "company_name": company,
        "goal": goal,
        "identity": identity,
        "language": language,
        "email_tone": tone,
        "auto_reply_mode": mode,
    }
    if country:
        payload["country"] = country
    if industry:
        payload["industry"] = industry
    if contact_name:
        payload["contact_name"] = contact_name
    if contact_email:
        payload["contact_email"] = contact_email
    if contact_role:
        payload["contact_role"] = contact_role
    if cc:
        payload["cc"] = cc
    if extra_context:
        payload["extra_context"] = extra_context

    try:
        resp = httpx.post(f"{url}/api/research/", json=payload, headers=headers, timeout=10)
        data = resp.json()
        if as_json:
            _output(data, True)
        else:
            if resp.status_code == 201:
                campaign_id = data.get('campaign_id')
                click.echo(f"Research started for {company}")
                click.echo(f"  Campaign ID: {campaign_id}")
                click.echo(f"  Status: {data.get('status')}")
                if watch:
                    click.echo(f"  Watching progress...")
                    _watch_campaign(campaign_id, url, headers)
                else:
                    click.echo(f"  Track: ghostpost research status {campaign_id}")
                    click.echo(f"  Live:  ghostpost research run ... --watch")
            else:
                click.echo(f"Error: {data.get('detail', resp.text)}", err=True)
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("status")
@click.argument("campaign_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
@click.option("--watch", "watch", is_flag=True, help="Watch progress until pipeline completes")
def research_status(campaign_id, url, as_json, watch) -> None:
    """Check status of a research campaign."""
    headers = _get_headers(url)
    try:
        resp = httpx.get(f"{url}/api/research/{campaign_id}", headers=headers, timeout=10)
        data = resp.json()
        if as_json:
            _output(data, True)
        else:
            if resp.status_code == 200:
                click.echo(f"Campaign #{data['id']}: {data['company_name']}")
                click.echo(f"  Status: {data['status']} (phase {data['phase']}/{MAX_PHASES})")
                click.echo(f"  Goal: {data['goal']}")
                click.echo(f"  Identity: {data['identity']}")
                if data.get('error'):
                    click.echo(f"  Error: {data['error']}")
                if data.get('email_subject'):
                    click.echo(f"  Email: {data['email_subject']}")
                if data.get('thread_id'):
                    click.echo(f"  Thread: #{data['thread_id']}")

                # Always show verbose log history
                research_data = data.get("research_data") or {}
                verbose_log = research_data.get("verbose_log", [])
                if verbose_log:
                    click.echo(f"  --- Verbose Log ({len(verbose_log)} entries) ---")
                    for entry in verbose_log:
                        ts = entry.get("ts", "")
                        p = entry.get("phase", 0)
                        msg = entry.get("msg", "")
                        phase_tag = f"P{p}" if p > 0 else "--"
                        click.echo(f"  [{ts}] [{phase_tag}] {msg}")

                if watch and data['status'] not in ('sent', 'draft_pending', 'completed', 'failed', 'skipped'):
                    click.echo(f"  Watching progress...")
                    _watch_campaign(campaign_id, url, headers)
            else:
                click.echo(f"Error: {data.get('detail', resp.text)}", err=True)
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("list")
@click.option("--status", "filter_status", default=None, help="Filter by status")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_list(filter_status, url, as_json) -> None:
    """List research campaigns."""
    headers = _get_headers(url)
    params = {}
    if filter_status:
        params["status"] = filter_status

    try:
        resp = httpx.get(f"{url}/api/research/", params=params, headers=headers, timeout=10)
        data = resp.json()
        if as_json:
            _output(data, True)
        else:
            items = data.get("items", [])
            if not items:
                click.echo("No campaigns found.")
                return
            click.echo(f"{'ID':>4}  {'Company':<25}  {'Status':<16}  {'Phase':>5}  {'Identity':<15}")
            click.echo("-" * 75)
            for c in items:
                click.echo(
                    f"{c['id']:>4}  {c['company_name'][:25]:<25}  {c['status']:<16}  "
                    f"{c['phase']:>5}  {c['identity'][:15]:<15}"
                )
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("batch")
@click.argument("file", type=click.Path(exists=True))
@click.option("--name", default=None, help="Batch name (default: filename)")
@click.option("--defaults", "defaults_str", default=None, help="JSON string or file path with batch defaults")
@click.option("--dry-run", "dry_run", is_flag=True, help="Preview parsed companies without starting batch")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_batch(file, name, defaults_str, dry_run, url, as_json) -> None:
    """Start batch research from a JSON or CSV file.

    Accepts .json or .csv files. CSV files use smart column detection.

    \b
    JSON format:
    {
        "companies": [{"company_name": "...", "goal": "...", ...}, ...],
        "defaults": {"identity": "...", "language": "...", ...}
    }

    \b
    CSV format:
    company,contact_name,email,role,goal,industry,country
    Acme Corp,John Silva,john@acme.pt,CEO,Partnership,Tech,PT
    """
    headers = _get_headers(url)
    batch_name = name or os.path.splitext(os.path.basename(file))[0]

    # Parse --defaults (JSON string or file path)
    defaults = None
    if defaults_str:
        if os.path.isfile(defaults_str):
            try:
                with open(defaults_str) as df:
                    defaults = json.load(df)
            except Exception as e:
                click.echo(f"Error reading defaults file: {e}", err=True)
                raise SystemExit(1)
        else:
            try:
                defaults = json.loads(defaults_str)
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON in --defaults: {e}", err=True)
                raise SystemExit(1)

    ext = os.path.splitext(file)[1].lower()

    if ext == ".csv":
        # CSV path — use local parser for dry-run, API for execution
        from src.research.batch_import import parse_csv_file

        result = parse_csv_file(file, defaults)

        if result.errors:
            for err in result.errors:
                click.echo(f"  ERROR: {err}", err=True)
            raise SystemExit(1)

        if dry_run:
            if as_json:
                _output({
                    "companies": result.companies,
                    "warnings": result.warnings,
                    "column_mapping": result.column_mapping,
                    "total": len(result.companies),
                }, True)
            else:
                click.echo(f"CSV Preview: {len(result.companies)} companies")
                if result.warnings:
                    click.echo(f"  Warnings:")
                    for w in result.warnings:
                        click.echo(f"    - {w}")
                click.echo(f"  Column mapping: {result.column_mapping}")
                click.echo()
                for i, c in enumerate(result.companies, 1):
                    click.echo(f"  {i}. {c.get('company_name', '?')}"
                               f" | {c.get('contact_name', '-')}"
                               f" | {c.get('contact_email', '-')}"
                               f" | {c.get('goal', '-')}")
            return

        # Execute: send to batch API
        payload = {
            "name": batch_name,
            "companies": result.companies,
            "defaults": defaults,
        }
    else:
        # JSON path (original behavior)
        try:
            with open(file) as f:
                batch_data = json.load(f)
        except Exception as e:
            click.echo(f"Error reading file: {e}", err=True)
            raise SystemExit(1)

        if dry_run:
            companies = batch_data.get("companies", [])
            if as_json:
                _output({"companies": companies, "total": len(companies)}, True)
            else:
                click.echo(f"JSON Preview: {len(companies)} companies")
                for i, c in enumerate(companies, 1):
                    click.echo(f"  {i}. {c.get('company_name', '?')} | {c.get('goal', '-')}")
            return

        payload = {
            "name": batch_name,
            "companies": batch_data.get("companies", []),
            "defaults": defaults or batch_data.get("defaults"),
        }

    try:
        resp = httpx.post(f"{url}/api/research/batch", json=payload, headers=headers, timeout=10)
        data = resp.json()
        if as_json:
            _output(data, True)
        else:
            if resp.status_code == 201:
                click.echo(f"Batch started: {batch_name}")
                click.echo(f"  Batch ID: {data.get('batch_id')}")
                click.echo(f"  Companies: {data.get('total_companies')}")
                click.echo(f"  Track: ghostpost research queue {data.get('batch_id')}")
            else:
                click.echo(f"Error: {data.get('detail', resp.text)}", err=True)
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("queue")
@click.argument("batch_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_queue(batch_id, url, as_json) -> None:
    """Check queue status for a batch."""
    headers = _get_headers(url)
    try:
        resp = httpx.get(f"{url}/api/research/batch/{batch_id}", headers=headers, timeout=10)
        data = resp.json()
        if as_json:
            _output(data, True)
        else:
            if resp.status_code == 200:
                click.echo(f"Batch #{data['batch_id']}: {data['name']}")
                click.echo(f"  Status: {data['status']}")
                click.echo(
                    f"  Progress: {data['completed']}/{data['total_companies']} "
                    f"(failed: {data['failed']}, skipped: {data['skipped']})"
                )
                click.echo()
                campaigns = data.get("campaigns", [])
                for c in campaigns:
                    status_icon = {
                        "sent": "[sent]",
                        "draft_pending": "[draft]",
                        "failed": "[failed]",
                        "skipped": "[skipped]",
                        "queued": "[queued]",
                    }.get(c["status"], "[running]")
                    click.echo(f"  {status_icon} {c['company_name']}: {c['status']} (phase {c['phase']})")
            else:
                click.echo(f"Error: {data.get('detail', resp.text)}", err=True)
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("pause")
@click.argument("batch_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_pause(batch_id, url, as_json) -> None:
    """Pause a running batch."""
    headers = _get_headers(url)
    try:
        resp = httpx.post(f"{url}/api/research/batch/{batch_id}/pause", headers=headers, timeout=10)
        data = resp.json()
        _output(data, as_json, f"Batch {batch_id} paused.")
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("resume")
@click.argument("batch_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_resume(batch_id, url, as_json) -> None:
    """Resume a paused batch."""
    headers = _get_headers(url)
    try:
        resp = httpx.post(f"{url}/api/research/batch/{batch_id}/resume", headers=headers, timeout=10)
        data = resp.json()
        _output(data, as_json, f"Batch {batch_id} resumed.")
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("skip")
@click.argument("campaign_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_skip(campaign_id, url, as_json) -> None:
    """Skip a queued campaign."""
    headers = _get_headers(url)
    try:
        resp = httpx.post(f"{url}/api/research/{campaign_id}/skip", headers=headers, timeout=10)
        data = resp.json()
        _output(data, as_json, f"Campaign {campaign_id} skipped.")
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("retry")
@click.argument("campaign_id", type=int)
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_retry(campaign_id, url, as_json) -> None:
    """Retry a failed campaign."""
    headers = _get_headers(url)
    try:
        resp = httpx.post(f"{url}/api/research/{campaign_id}/retry", headers=headers, timeout=10)
        data = resp.json()
        _output(data, as_json, f"Campaign {campaign_id} queued for retry.")
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("output")
@click.argument("campaign_id", type=int)
@click.argument("filename")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_output(campaign_id, filename, url, as_json) -> None:
    """Read a research phase output file."""
    headers = _get_headers(url)
    try:
        resp = httpx.get(
            f"{url}/api/research/{campaign_id}/output/{filename}",
            headers=headers, timeout=30,
        )
        if resp.status_code == 404:
            if as_json:
                click.echo(json.dumps({"ok": False, "error": "Output file not found", "code": "HTTP_4XX", "retryable": False}))
            else:
                click.echo(f"Error: Output file '{filename}' not found for campaign #{campaign_id}", err=True)
            raise SystemExit(1)
        resp.raise_for_status()
        content = resp.text
        if as_json:
            _output({"campaign_id": campaign_id, "filename": filename, "content": content}, True)
        else:
            click.echo(content)
    except SystemExit:
        raise
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)


@research_group.command("identities")
@click.option("--url", default="http://127.0.0.1:8000", help="API base URL")
@click.option("--json", "as_json", is_flag=True, help="JSON output")
def research_identities(url, as_json) -> None:
    """List available sender identities."""
    headers = _get_headers(url)
    try:
        resp = httpx.get(f"{url}/api/research/identities", headers=headers, timeout=10)
        data = resp.json()
        if as_json:
            _output(data, True)
        else:
            if not data:
                click.echo("No identities found. Create one in config/identities/")
                return
            for ident in data:
                click.echo(f"  {ident['id']}: {ident.get('company_name', '')} ({ident.get('sender_email', '')})")
    except Exception as e:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(e), "code": "CONNECTION_ERROR", "retryable": True}))
        else:
            click.echo(f"Could not reach API: {e}", err=True)
        raise SystemExit(1)
