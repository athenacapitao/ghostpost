# CLI Full Coverage Plan — GhostPost

> **Goal:** 100% CLI coverage of all 92 API endpoints + updated OpenClaw skills
> **Current:** 55 CLI commands → **Target:** 71 CLI commands (16 new + 1 flag enhancement)
> **Created:** 2026-02-25

---

## Executive Summary

GhostPost has 92 API endpoints but only 55 CLI commands — 85% coverage. For an agent-first system, this is unacceptable. OpenClaw (Athena) must be able to perform every action via CLI with `--json` output. This plan closes every gap and updates all 12 OpenClaw skills.

---

## Gap Analysis

### Missing CLI Commands (16 endpoints)

| # | API Endpoint | What's Missing | Priority |
|---|-------------|----------------|----------|
| 1 | `GET /api/contacts` | List contacts | HIGH — core read |
| 2 | `GET /api/contacts/{id}` | View contact detail | HIGH — core read |
| 3 | `PUT /api/threads/{id}/notes` | Set thread notes | HIGH — agent context |
| 4 | `POST /api/threads/{id}/extract` | Trigger outcome extraction | HIGH — agent workflow |
| 5 | `GET /api/notifications/alerts` | Read notification alerts | MEDIUM — awareness |
| 6 | `GET /api/security/events` | List ALL security events | MEDIUM — security audit |
| 7 | `GET /api/attachments/{id}/download` | Download attachment | MEDIUM — data access |
| 8 | `GET /api/batch` | List enrichment batch jobs | LOW — ops |
| 9 | `GET /api/batch/{id}` | Batch job detail | LOW — ops |
| 10 | `POST /api/batch/{id}/cancel` | Cancel batch job | LOW — ops |
| 11 | `PUT /api/playbooks/{name}` | Update playbook content | MEDIUM — CRUD gap |
| 12 | `PUT /api/settings/bulk` | Bulk update settings | LOW — convenience |
| 13 | `DELETE /api/settings/{key}` | Delete/reset a setting | LOW — cleanup |
| 14 | `GET /api/research/{id}/output/{fn}` | Read research output file | HIGH — agent workflow |
| 15 | `generate-reply` missing `--draft` | Auto-create draft with gen | HIGH — key workflow |
| 16 | `POST /api/playbooks` (update variant) | Update playbook body | MEDIUM — CRUD completion |

### Intentionally Excluded (browser/session-only)

| Endpoint | Reason |
|----------|--------|
| `POST /api/auth/login` | CLI auto-authenticates via JWT |
| `POST /api/auth/logout` | No session to end in CLI |
| `GET /api/auth/me` | CLI knows who it is |
| `WS /api/ws` | WebSocket — browser real-time only |

---

## Implementation Plan

### Batch 1: Core Read Commands (Steps 1-2)

**No dependencies. Can be built in parallel.**

#### Step 1: Contacts CLI — `src/cli/contacts.py` (NEW FILE)

```python
# Commands:
ghostpost contacts [--limit N] [--search QUERY] [--json]   # GET /api/contacts
ghostpost contact <contact_id> [--json]                     # GET /api/contacts/{id}
```

**File:** `src/cli/contacts.py`
- `contacts_cmd`: Click command, `@json_option`, calls `api_get("/api/contacts", params={...})`
- `contact_cmd`: Click command, `@json_option`, calls `api_get(f"/api/contacts/{contact_id}")`
- Human output: table for list, detail block for single contact (name, email, company, relationship, topics, last interaction)
- JSON output: standard `format_result(data, as_json)` envelope

**Register in:** `src/cli/main.py` — `cli.add_command(contacts_cmd)`, `cli.add_command(contact_cmd)`

#### Step 2: Thread Notes — `src/cli/threads.py` (MODIFY)

```python
# Command:
ghostpost notes <thread_id> --text "Important: follow up Monday" [--json]  # PUT /api/threads/{id}/notes
ghostpost notes <thread_id> [--json]                                        # GET (show current notes)
```

**File:** `src/cli/threads.py` — add `notes_cmd`
- With `--text`: calls `api_put(f"/api/threads/{thread_id}/notes", json={"notes": text})`
- Without `--text`: calls `api_get(f"/api/threads/{thread_id}")` and displays `.notes` field
- Register in `src/cli/main.py`

---

### Batch 2: Agent Workflow Commands (Steps 3-5)

**No dependencies. Can be built in parallel.**

#### Step 3: Outcomes Extract — `src/cli/outcomes.py` (MODIFY)

```python
# Command:
ghostpost outcomes extract <thread_id> [--json]  # POST /api/threads/{id}/extract
```

**File:** `src/cli/outcomes.py` — add `extract` subcommand to `outcomes_group`
- Calls `api_post(f"/api/threads/{thread_id}/extract")`
- Human output: extracted outcome summary (type, topic, agreements, lessons)
- No new registration needed (already registered as group)

#### Step 4: Notifications Alerts — `src/cli/notifications.py` (NEW FILE)

```python
# Command:
ghostpost alerts [--json]  # GET /api/notifications/alerts
```

**File:** `src/cli/notifications.py`
- `alerts_cmd`: calls `api_get("/api/notifications/alerts")`
- Human output: table of alert type, severity, message, timestamp
- Register in `src/cli/main.py`

#### Step 5: Generate Reply with --draft — `src/cli/actions.py` (MODIFY)

```python
# Enhanced command:
ghostpost generate-reply <thread_id> [--instructions "..."] [--style ...] [--draft] [--json]
```

**File:** `src/cli/actions.py` — modify `generate_reply_cmd`
- Add `@click.option("--draft", is_flag=True, help="Auto-create draft from generated reply")`
- When `--draft` is set, add `create_draft=True` to request params/body
- No new registration needed

---

### Batch 3: Security & Data Commands (Steps 6-8)

**No dependencies. Can be built in parallel.**

#### Step 6: Security Events — `src/cli/security.py` (MODIFY)

```python
# Command:
ghostpost security-events [--limit N] [--json]  # GET /api/security/events
```

**File:** `src/cli/security.py` — add `security_events_cmd`
- Calls `api_get("/api/security/events", params={...})`
- Human output: table of event_id, type, severity, thread_id, timestamp, status
- Register in `src/cli/main.py`

#### Step 7: Attachment Download — `src/cli/attachments.py` (NEW FILE)

```python
# Command:
ghostpost attachment <attachment_id> [--output PATH] [--json]  # GET /api/attachments/{id}/download
```

**File:** `src/cli/attachments.py`
- **Special handling:** API returns binary `FileResponse`, not JSON
- Use `get_api_client().get(url, headers=headers)` directly (NOT `api_get()`)
- Parse `Content-Disposition` header for filename
- Save to `--output` path or `./attachments/{filename}`
- JSON mode: return `{"ok": true, "data": {"path": "/saved/path", "size": 1234, "filename": "doc.pdf"}}`
- Human mode: `"Saved: doc.pdf (1234 bytes) → ./attachments/doc.pdf"`
- Register in `src/cli/main.py`

#### Step 8: Research Output — `src/cli/research.py` (MODIFY)

```python
# Command:
ghostpost research output <campaign_id> <filename> [--json]  # GET /api/research/{id}/output/{filename}
```

**File:** `src/cli/research.py` — add `output` subcommand to `research_group`
- Calls research API directly (follows module's own auth pattern with `_get_headers()`)
- Response is plain text (markdown). Print directly in human mode.
- JSON mode: `{"ok": true, "data": {"filename": "...", "content": "..."}}`
- No new registration needed

---

### Batch 4: CRUD Completion (Steps 9-11)

**No dependencies. Can be built in parallel.**

#### Step 9: Playbook Update — `src/cli/playbooks.py` (MODIFY)

```python
# Command:
ghostpost playbook-update <name> --body "## Updated content..." [--json]  # PUT /api/playbooks/{name}
```

**File:** `src/cli/playbooks.py` — add `playbook_update_cmd`
- Calls `api_put(f"/api/playbooks/{name}", content=body)` (plaintext PUT, matching API)
- Register in `src/cli/main.py`

#### Step 10: Settings Extensions — `src/cli/settings.py` (MODIFY)

```python
# Extended commands:
ghostpost settings delete <key> [--json]                    # DELETE /api/settings/{key}
ghostpost settings bulk <key1=val1> [key2=val2] ... [--json] # PUT /api/settings/bulk
```

**File:** `src/cli/settings.py` — extend `settings_cmd`
- Add `"delete"` and `"bulk"` to the action `Choice`
- `delete`: calls `api_delete(f"/api/settings/{key}")`
- `bulk`: parse variadic `key=value` pairs, calls `api_put("/api/settings/bulk", json={"settings": dict})`
- No new registration needed

#### Step 11: Batch Jobs CLI — `src/cli/batch.py` (NEW FILE)

```python
# Commands (Click group):
ghostpost batch list [--json]              # GET /api/batch
ghostpost batch detail <batch_id> [--json]  # GET /api/batch/{id}
ghostpost batch cancel <batch_id> [--json]  # POST /api/batch/{id}/cancel
```

**File:** `src/cli/batch.py`
- `batch_group`: Click group named `batch`
- `list` subcommand: calls `api_get("/api/batch")`
- `detail` subcommand: calls `api_get(f"/api/batch/{batch_id}")`
- `cancel` subcommand: calls `api_post(f"/api/batch/{batch_id}/cancel")`
- Register group in `src/cli/main.py`

---

### Batch 5: Registration & Integration (Step 12)

**Depends on: Batches 1-4**

#### Step 12: Register All Commands — `src/cli/main.py` (MODIFY)

Add imports and registrations:

```python
# New imports:
from src.cli.contacts import contacts_cmd, contact_cmd
from src.cli.threads import notes_cmd  # (added to existing import)
from src.cli.notifications import alerts_cmd
from src.cli.security import security_events_cmd  # (added to existing import)
from src.cli.attachments import attachment_cmd
from src.cli.batch import batch_group
from src.cli.playbooks import playbook_update_cmd  # (added to existing import)

# New registrations:
cli.add_command(contacts_cmd)
cli.add_command(contact_cmd)
cli.add_command(notes_cmd)
cli.add_command(alerts_cmd)
cli.add_command(security_events_cmd)
cli.add_command(attachment_cmd)
cli.add_command(batch_group)
cli.add_command(playbook_update_cmd)
```

---

### Batch 6: Update Thread Context Files (Step 13)

**Depends on: Batch 5**

#### Step 13: Update "Available Actions" in context_writer.py

**File:** `src/engine/context_writer.py`

Update the `_write_thread_file()` method to include new commands in the "Available Actions" section of per-thread context files (`context/threads/{id}.md`):

- Add `ghostpost notes {id} --text "..." --json` for all threads
- Add `ghostpost outcomes extract {id} --json` for threads in GOAL_MET or ARCHIVED state
- Add `ghostpost attachment {att_id} --json` when thread has attachments

---

### Batch 7: Tests (Step 14)

**Depends on: Batches 1-5**

#### Step 14: Test All New Commands — `tests/test_cli_full_coverage.py` (NEW FILE)

Test pattern (follow `tests/test_cli_json_flag.py` exactly):

```python
from click.testing import CliRunner
from unittest.mock import patch

# For each new command:
# 1. Test --help contains --json
# 2. Test JSON output returns {"ok": true, "data": ...} envelope
# 3. Test human-readable output
# 4. Test error handling (connection error, HTTP error)
```

**Test count:** ~50 tests total

| Command | Tests |
|---------|-------|
| `contacts` | 3 (help, json list, human list) |
| `contact <id>` | 3 (help, json detail, human detail) |
| `notes` | 4 (help, set notes, get notes, json) |
| `outcomes extract` | 3 (help, json, human) |
| `alerts` | 3 (help, json, human) |
| `security-events` | 3 (help, json, human) |
| `attachment` | 4 (help, json, human, binary download) |
| `batch list` | 3 (help, json, human) |
| `batch detail` | 3 (help, json, human) |
| `batch cancel` | 3 (help, json, human) |
| `playbook-update` | 3 (help, json, human) |
| `settings delete` | 3 (help, json, human) |
| `settings bulk` | 3 (help, json, human) |
| `research output` | 3 (help, json, human) |
| `generate-reply --draft` | 2 (flag present, draft param sent) |

---

### Batch 8: Update OpenClaw Skills (Step 15)

**Depends on: Batches 1-5**

#### Step 15: Update All 12 Skills

Each update consists of modifying `SKILL.md` (quick start, workflow sections) and `references/cli-reference.md` (full command docs).

##### 15a. ghostpost-read — ADD contacts + attachments

**SKILL.md changes:**
- Add to Quick Start:
  ```
  ghostpost contacts --json                # List all contacts
  ghostpost contact <id> --json            # Contact detail
  ghostpost attachment <id> --json         # Download attachment
  ```
- Add "Contacts" section to Workflow
- Add "Attachments" to Tips

**cli-reference.md changes:**
- Add full `ghostpost contacts` command docs (options, output format)
- Add full `ghostpost contact <id>` command docs
- Add full `ghostpost attachment <id>` command docs
- Add API endpoint table entries

##### 15b. ghostpost-search — ADD contact search

**cli-reference.md changes:**
- Add mention of `ghostpost contacts --search "query"` as alternative to email search

##### 15c. ghostpost-reply — ADD --draft to generate-reply

**SKILL.md changes:**
- Replace curl example in "AI-Generated Replies" with:
  ```
  ghostpost generate-reply <id> --instructions "Be concise" --draft --json
  ```

**cli-reference.md changes:**
- Add `--draft` flag documentation to `generate-reply` entry
- Remove curl examples

##### 15d. ghostpost-compose — ADD batch job awareness

**cli-reference.md changes:**
- Add note: "For bulk sends (>20 recipients), compose auto-creates batch job. Manage with `ghostpost batch list/detail/cancel`"

##### 15e. ghostpost-manage — ADD notes, batch, settings extensions

**SKILL.md changes:**
- Add `ghostpost notes <id> --text "..."` to Common Operations
- Add batch management section

**cli-reference.md changes:**
- Add full `ghostpost notes` command docs
- Add `ghostpost batch list/detail/cancel` command docs
- Add `ghostpost settings delete` and `ghostpost settings bulk` docs

##### 15f. ghostpost-goals — NO CHANGES

Already complete.

##### 15g. ghostpost-security — ADD security events

**SKILL.md changes:**
- Add `ghostpost security-events --json` to Quick Start
- Add to Workflow step 5: "Review all security events"

**cli-reference.md changes:**
- Add full `ghostpost security-events` command docs with options
- Add API endpoint entry

##### 15h. ghostpost-context — UPDATE cross-references

**SKILL.md changes:**
- Add `ghostpost alerts --json` mention in workflow step for checking alerts
- Add cross-reference to `ghostpost contacts` for contact exploration

##### 15i. ghostpost-notify — ADD alerts command

**SKILL.md changes:**
- Add `ghostpost alerts --json` to Quick Start (currently only shows settings commands)
- Add Workflow step: "Check active alerts"

**cli-reference.md changes:**
- Add full `ghostpost alerts` command docs

##### 15j. ghostpost-playbook — ADD playbook-update

**SKILL.md changes:**
- Add `ghostpost playbook-update <name> --body "..."` to Quick Start

**cli-reference.md changes:**
- Add full `ghostpost playbook-update` command docs

##### 15k. ghostpost-outcomes — ADD extract

**SKILL.md changes:**
- Replace curl example with: `ghostpost outcomes extract <thread_id> --json`
- Add to Workflow step 3

**cli-reference.md changes:**
- Add full `ghostpost outcomes extract` command docs
- Remove curl example

##### 15l. ghostpost-research — ADD output command

**SKILL.md changes:**
- Add `ghostpost research output <id> 05_email_draft.md --json` to Quick Start
- Update "Review output" workflow step

**cli-reference.md changes:**
- Add full `ghostpost research output` command docs
- Add API endpoint entry

---

## File Change Summary

### New Files (4)

| File | Purpose |
|------|---------|
| `src/cli/contacts.py` | Contacts list + detail |
| `src/cli/notifications.py` | Alerts command |
| `src/cli/attachments.py` | Attachment download |
| `src/cli/batch.py` | Enrichment batch management |

### Modified Files — GhostPost (7)

| File | Changes |
|------|---------|
| `src/cli/threads.py` | Add `notes_cmd` |
| `src/cli/outcomes.py` | Add `extract` subcommand |
| `src/cli/actions.py` | Add `--draft` flag to `generate-reply` |
| `src/cli/security.py` | Add `security_events_cmd` |
| `src/cli/research.py` | Add `output` subcommand |
| `src/cli/playbooks.py` | Add `playbook_update_cmd` |
| `src/cli/settings.py` | Add `delete` and `bulk` actions |
| `src/cli/main.py` | Register all new commands |
| `src/engine/context_writer.py` | Update Available Actions |

### Modified Files — OpenClaw Skills (22)

| Skill | Files Changed |
|-------|--------------|
| ghostpost-read | SKILL.md + cli-reference.md |
| ghostpost-search | cli-reference.md |
| ghostpost-reply | SKILL.md + cli-reference.md |
| ghostpost-compose | cli-reference.md |
| ghostpost-manage | SKILL.md + cli-reference.md |
| ghostpost-security | SKILL.md + cli-reference.md |
| ghostpost-context | SKILL.md |
| ghostpost-notify | SKILL.md + cli-reference.md |
| ghostpost-playbook | SKILL.md + cli-reference.md |
| ghostpost-outcomes | SKILL.md + cli-reference.md |
| ghostpost-research | SKILL.md + cli-reference.md |

### New Test File (1)

| File | Tests |
|------|-------|
| `tests/test_cli_full_coverage.py` | ~50 tests |

---

## Execution Order

```
Batch 1-4 (ALL PARALLEL — no dependencies between them):
  ├── Step 1:  contacts.py (new)
  ├── Step 2:  notes_cmd (threads.py)
  ├── Step 3:  outcomes extract (outcomes.py)
  ├── Step 4:  alerts (notifications.py, new)
  ├── Step 5:  generate-reply --draft (actions.py)
  ├── Step 6:  security-events (security.py)
  ├── Step 7:  attachment download (attachments.py, new)
  ├── Step 8:  research output (research.py)
  ├── Step 9:  playbook-update (playbooks.py)
  ├── Step 10: settings delete/bulk (settings.py)
  └── Step 11: batch group (batch.py, new)

Batch 5 (SEQUENTIAL — needs all above):
  └── Step 12: main.py registration

Batch 6 (SEQUENTIAL — needs Batch 5):
  └── Step 13: context_writer.py (Available Actions)

Batch 7 (SEQUENTIAL — needs Batch 5):
  └── Step 14: tests/test_cli_full_coverage.py

Batch 8 (PARALLEL with Batch 7 — needs Batch 5):
  └── Step 15a-l: All 12 OpenClaw skill updates
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Attachment download is binary, not JSON | `api_get()` will fail | Use `get_api_client()` directly with streaming |
| Settings bulk parsing complexity | Click arg parsing edge cases | Use `nargs=-1` for variadic `key=value` pairs |
| Research module uses own auth pattern | Inconsistency | Follow existing module pattern, don't refactor |
| Large number of skill file edits | Typo/inconsistency risk | Review all skills after update for cross-reference accuracy |
| Context writer changes affect existing threads | Wrong "Available Actions" | Only add new commands where relevant (e.g., extract only for completed threads) |

---

## Definition of Done

- [ ] 71 CLI commands covering ALL 92 API endpoints (excluding 4 browser-only)
- [ ] All new commands support `--json` with `{"ok": true, "data": ...}` envelope
- [ ] `ghostpost --help` lists all commands cleanly
- [ ] `generate-reply --draft` creates draft in one step
- [ ] Per-thread context files show new commands in "Available Actions"
- [ ] All 12 OpenClaw skills updated — no curl examples remain, all CLI commands documented
- [ ] ~50 new tests passing
- [ ] 0 regressions on existing 792 tests
- [ ] Total test count: ~842

---

## Post-Implementation Verification

```bash
# 1. Verify all commands registered
ghostpost --help

# 2. Verify JSON support
for cmd in contacts alerts security-events notes; do
  ghostpost $cmd --help | grep -q "\-\-json" && echo "OK: $cmd" || echo "FAIL: $cmd"
done

# 3. Run full test suite
cd /home/athena/ghostpost && python -m pytest tests/ -v --tb=short

# 4. Verify OpenClaw skills reference new commands
grep -r "ghostpost contacts" /home/athena/openclaw/skills/ghostpost-read/
grep -r "ghostpost alerts" /home/athena/openclaw/skills/ghostpost-notify/
grep -r "ghostpost outcomes extract" /home/athena/openclaw/skills/ghostpost-outcomes/
grep -r "ghostpost research output" /home/athena/openclaw/skills/ghostpost-research/
grep -r "generate-reply.*--draft" /home/athena/openclaw/skills/ghostpost-reply/
```
