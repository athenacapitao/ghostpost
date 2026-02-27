# GhostPost — OpenClaw Integration Reference
<!-- schema_version: 1 -->

> Extracted from MASTER_PLAN.md Section 5

---

## Integration Model

Same machine: GhostPost at `/home/athena/ghostpost`, OpenClaw at `/home/athena/openclaw`.

**Hybrid approach:**
- **Files** — OpenClaw reads/writes living markdown context files
- **CLI** — `ghostpost` command for all actions
- **Direct access** — Agent can read source code, DB, and any file

---

## Living Context Files

Location: `/home/athena/ghostpost/context/`

Updated incrementally on every event — these are the agent's primary source of truth:

Each file has `<!-- schema_version: 1 -->` on line 2. The version increments only on structural schema changes, not content updates.

| File | Purpose | Update Trigger |
|------|---------|---------------|
| `README.md` | Entry point: index of all files and CLI quick reference | Manual / on schema change |
| `SYSTEM_BRIEF.md` | Dashboard: API health, inbox counts, priorities, pending goals | Every sync |
| `EMAIL_CONTEXT.md` | Active threads, priorities, pending goals, draft queue | New email, state change, goal update |
| `CONTACTS.md` | Known contacts with full profiles | After each interaction |
| `RULES.md` | Reply style, blocklists, auto-reply rules, follow-up defaults, playbook index | User changes settings |
| `ACTIVE_GOALS.md` | All threads with active goals, acceptance criteria, status | Goal created/updated/met |
| `DRAFTS.md` | Pending drafts awaiting approval | Draft created/approved/rejected |
| `SECURITY_ALERTS.md` | Quarantined emails, injection attempts, anomalies | Security event detected |
| `ALERTS.md` | Follow-up reminders, stale threads, system notifications (broader scope than SECURITY_ALERTS.md) | Every sync |

---

## OpenClaw Skills (10)

Each skill is a `SKILL.md` file installed in OpenClaw's skill directory:

| Skill | Purpose | CLI Commands |
|-------|---------|-------------|
| `ghostpost-read` | Search and read emails/threads | `ghostpost search`, `ghostpost thread`, `ghostpost email` |
| `ghostpost-reply` | Compose and send replies | `ghostpost reply`, `ghostpost draft` |
| `ghostpost-compose` | Start new email threads | `ghostpost compose` |
| `ghostpost-manage` | Update goals, toggles, timers, settings | `ghostpost goal`, `ghostpost toggle`, `ghostpost followup` |
| `ghostpost-context` | Read/update context files, contact profiles | `ghostpost context`, `ghostpost contact` |
| `ghostpost-search` | Advanced search across emails, contacts, threads | `ghostpost search` (with filters) |
| `ghostpost-goals` | Goal lifecycle, acceptance criteria testing | `ghostpost goal`, `ghostpost criteria` |
| `ghostpost-playbook` | Load and follow playbook templates | `ghostpost playbook` |
| `ghostpost-security` | Check scores, review quarantine, manage blocklists | `ghostpost security`, `ghostpost quarantine` |
| `ghostpost-notify` | Control notification preferences and triggers | `ghostpost notify` |

---

## CLI Tool: `ghostpost`

All commands accept `--json` which returns a structured envelope: `{"ok": true, "data": {...}}`. Always use `--json` in agent scripts for reliable parsing.

### Recommended First Command
```bash
ghostpost status --json          # Health + live inbox snapshot; read this before any action
```

### Reading
```bash
ghostpost threads --json                      # List threads (default 20)
ghostpost threads --state ACTIVE --json       # Filter by state
ghostpost thread <id> --json                  # Full thread with all emails
ghostpost email <id> --json                   # Single email details
ghostpost search "keyword" --json             # Search by subject/body/sender
ghostpost brief <id> --json                   # AI-generated structured thread brief
```

### Actions
```bash
ghostpost reply <thread_id> --body "..." --json       # Send reply immediately
ghostpost draft <thread_id> --to x@y --subject ".." --body "..." --json  # Create draft for approval
ghostpost drafts --json                               # List pending drafts
ghostpost draft-approve <draft_id> --json             # Approve and send draft
ghostpost draft-reject <draft_id> --json              # Reject draft
ghostpost compose --to x@y.com --subject ".." --body "..." --json  # New email thread
ghostpost generate-reply <thread_id> --json           # AI-generate a reply draft
```

### Management
```bash
ghostpost goal <thread_id> --set "Negotiate to €5k" --json
ghostpost goal <thread_id> --criteria "Price agreed in writing" --json
ghostpost goal <thread_id> --check --json             # LLM check if goal is met
ghostpost goal <thread_id> --status met --json
ghostpost goal <thread_id> --clear --json
ghostpost state <thread_id> <STATE> --json            # NEW/ACTIVE/WAITING_REPLY/FOLLOW_UP/GOAL_MET/ARCHIVED
ghostpost toggle <thread_id> --mode off|draft|auto --json
ghostpost followup <thread_id> --days 5 --json
ghostpost playbooks --json                            # List available playbooks
ghostpost playbook <name> --json                      # Show playbook content
ghostpost apply-playbook <thread_id> <name> --json    # Apply playbook to thread
ghostpost playbook-create <name> --body "..." --json
ghostpost playbook-delete <name> --json
```

### Enrichment / AI
```bash
ghostpost enrich --json                       # Run AI enrichment (categorize, summarize, analyze)
ghostpost enrich-web <contact_id> --json      # Web-enrich a contact via LLM inference
```

### Security
```bash
ghostpost quarantine list --json              # List quarantined emails
ghostpost quarantine approve <event_id> --json  # Release from quarantine
ghostpost quarantine dismiss <event_id> --json  # Dismiss event
ghostpost blocklist list --json               # View blocklist
ghostpost blocklist add <email> --json        # Add to blocklist
ghostpost blocklist remove <email> --json     # Remove from blocklist
ghostpost audit --json                        # Recent agent actions (24h default)
ghostpost audit --hours 48 --limit 50 --json
```

### Settings
```bash
ghostpost settings list --json
ghostpost settings get <key> --json
ghostpost settings set <key> <value> --json
```

### System
```bash
ghostpost sync --json                         # Force immediate Gmail sync
ghostpost stats --json                        # Storage usage, counts
ghostpost health --json                       # API health check (db, redis)
```

---

## Telegram Integration

User interacts with OpenClaw via Telegram, which uses Ghost Post skills:

- "Send an email to person@email.com about X" → `ghostpost-compose`
- "Reply to [person/thread] saying Y" → `ghostpost-reply`
- "Show me pending drafts" → `ghostpost-read`
- "Approve draft for [thread]" → `ghostpost-manage`
- "Set goal for [thread] to Z" → `ghostpost-goals`
- "What's the status of [thread/goal]?" → `ghostpost-read` + `ghostpost-goals`
