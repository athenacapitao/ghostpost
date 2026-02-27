# GhostPost Agent-First Architecture Report

**Research Date:** 2026-02-25  
**Model:** Haiku 4.5  
**Scope:** Complete agent-facing surface area analysis

---

## EXECUTIVE SUMMARY

GhostPost is **agent-first by design** — optimized for OpenClaw consumption through:

1. **73 API endpoints** structured by domain (threads, emails, drafts, goals, security, etc.)
2. **43 CLI commands** with `--json` support for structured output
3. **10 living context files** in markdown format auto-updated on sync
4. **1 skills framework** (Ghost Research) with standardized SKILL.md interface
5. **Atomic file operations** — context files never partially written
6. **Schema versioning** — every context file has `schema_version` on line 2

The architecture assumes **email content is untrusted data** — all untrusted email bodies are wrapped in `=== UNTRUSTED EMAIL CONTENT START/END ===` markers during context generation.

---

## 1. SKILLS FRAMEWORK

### Current State: 1 Skill Implemented

**Location:** `/home/athena/ghostpost/skills/`

```
skills/
└── ghost-research/
    └── SKILL.md          # Standardized skill definition
```

### Ghost Research SKILL.md Structure

**File:** `/home/athena/ghostpost/skills/ghost-research/SKILL.md`

```yaml
name: ghost-research
description: Deep company research pipeline...
user-invocable: true
```

**What It Does:**
- 8-phase research pipeline: Input → Deep Research → Opportunity Analysis → Contacts Search → Person Research (conditional) → Peer Intelligence → Value Proposition → Email Composition
- Produces research dossier + contacts + peer intelligence + tailored value prop + email draft
- Persists all output to `research/[company_slug]/00-06_*.md`
- Generates email in specified language (default pt-PT) with peer evidence

**Backend Support:**
- DB Models: `ResearchCampaign`, `ResearchBatch` (src/db/models.py)
- Engine: `src/research/` (12 modules: pipeline.py, queue.py, 8 phase modules + identities.py, web_research.py)
- API: 12 endpoints in `/api/research/*` (src/api/routes/research.py — 289 LOC)
- CLI: `ghostpost research` group (src/cli/research.py — 362 LOC)

**How OpenClaw Uses It:**
1. Read `RESEARCH.md` context file for status
2. Call API: `POST /api/research/` or `POST /api/research/batch`
3. Poll status: `GET /api/research/<campaign_id>` or `ghostpost research status <id> --json`
4. Manage queue: pause/resume/skip/retry via CLI or API
5. Read output: `GET /api/research/<campaign_id>/output/[phase].md` or directly from `research/[company_slug]/`

**Configuration:**
- Identity files: `config/identities/*.md` (YAML frontmatter + markdown body)
- Defaults: `config/ghost_research_defaults.md` (language, tone, email length, auto-reply mode)
- Search API: Requires `SEARCH_API_KEY` in .env (Serper API for web research)

---

## 2. CONTEXT FILES (Agent-Consumed Markdown)

**Location:** `/home/athena/ghostpost/context/`  
**Generator:** `src/engine/context_writer.py` (977 LOC)  
**Trigger:** Auto-updated on every sync; individual writes on state changes  
**Write Pattern:** Atomic (temp file → rename) to prevent partial reads

### Context File Inventory

| File | Purpose | Auto-Update Trigger | Rows | Key Fields |
|------|---------|-------------------|------|-----------|
| `SYSTEM_BRIEF.md` | Dashboard: health, inbox snapshot, priorities, pending items (start here) | Sync | ~50 lines | Counts (NEW/ACTIVE/WAITING_REPLY/FOLLOW_UP/ARCHIVED), unread, drafts, last sync, attention items table, active goals table, security counts, activity (24h) |
| `EMAIL_CONTEXT.md` | Active threads with sender, state, summary, category, priority, security score | Sync | ~5 lines per thread | Thread ID, subject, state, category, from, email count, auto-reply mode, follow-up schedule, summary, priority, last activity, goal (if set), playbook (if set), link to full thread file |
| `threads/*.md` | Individual thread detail: all emails with metadata, analysis, attachments | Sync | ~100-500 per thread | Metadata (state, category, priority, security score, participants, goal, playbook, follow-up, summary), messages (received/sent, direction, from/to, UNTRUSTED markers for incoming), analysis (sentiment, urgency, action_required), attachments |
| `threads/archive/*.md` | Archived thread details (moved after state=ARCHIVED) | State change | — | Same as threads/*.md |
| `CONTACTS.md` | Enriched contact profiles (role, company, communication style, topics) | After interaction | ~5 lines per contact | Email, name, relationship, frequency, preferred style, topics, last interaction, notes |
| `RULES.md` | Reply defaults, security thresholds, blocklist, never-auto-reply list, notification rules | Settings change | ~30 lines | Reply style, follow-up defaults, auto-reply default, security thresholds, blocklist entries, never-auto-reply entries, notification rules |
| `ACTIVE_GOALS.md` | All threads with active goals, acceptance criteria, status tracking | Goal change | ~5 lines per goal | Thread ID, subject, goal text, acceptance criteria, status (in_progress/met/abandoned), thread state, playbook (if set), auto-reply mode, follow-up schedule |
| `DRAFTS.md` | Pending drafts awaiting approval (with recipient, subject, preview) | Draft change | ~4 lines per draft | Draft ID, subject, to address, thread ID, created timestamp, body preview (200 chars) |
| `SECURITY_ALERTS.md` | Quarantined emails, injection attempts, anomaly events (pending resolution) | Security event | ~5 lines per event | Severity, event type, timestamp, email ID, thread ID, quarantine status, details |
| `RESEARCH.md` | Active research campaigns, batch status, recent completions | Research change | ~40 lines | Total campaigns, active count, batch count; active batches table (status, progress); in-progress campaigns (company, status/phase, goal, identity, error); recently completed table |
| `ALERTS.md` | Append-only: follow-up reminders, stale threads, system notifications | Real-time appends | Last 50 | Deduped (checks last 20 entries before append), trimmed on sync |

### Schema Versioning Pattern

Every context file starts:
```markdown
# Title
<!-- schema_version: 1 -->
<!-- optional: other comments -->
```

**Why:** Agents can parse version and handle breaking changes gracefully.

### Key Design Decisions

1. **Atomic writes:** No partial reads — all context files use temp+rename pattern
2. **Untrusted markers:** Received emails wrapped in `=== UNTRUSTED EMAIL CONTENT START/END ===`
3. **Thread isolation:** Per-thread markdown files in `threads/` + references in EMAIL_CONTEXT.md
4. **Dedup on ALERTS:** `cleanup_alerts()` removes duplicates, trims to last 50 on sync
5. **Hierarchy:** SYSTEM_BRIEF → EMAIL_CONTEXT → (per-thread files) is read order

---

## 3. CLI INTERFACE (Agent-Driven)

**Location:** `src/cli/`  
**Entry Point:** `src/cli/main.py` (83 LOC)  
**Base Command:** `ghostpost`  
**Total Commands:** 43 main commands + subcommands  
**Output:** All support `--json` flag for structured results  

### CLI Command Groups

#### System Status
```bash
ghostpost health --json              # DB + Redis health
ghostpost status --json              # Inbox snapshot (start here)
ghostpost stats --json               # Storage counts
ghostpost sync --json                # Trigger Gmail sync
```

#### Thread Management (9 commands)
```bash
ghostpost threads [--state STATE] [--page N] --json
ghostpost thread <id> --json                          # Full thread detail
ghostpost search "query" --json                       # Search subject/body/sender
ghostpost state <id> <NEW|ACTIVE|WAITING_REPLY|...> --json
ghostpost followup <id> --days 5 --json              # Set follow-up interval
ghostpost toggle <id> --mode off|draft|auto --json   # Set auto-reply mode
```

#### Email & Drafts (8 commands)
```bash
ghostpost email <id> --json                                           # Single email
ghostpost reply <thread_id> --body "..." [--cc x@y] --json           # Send reply
ghostpost draft <thread_id> --to x@y --subject "..." --body "..." --json  # Create draft
ghostpost compose --to x@y --subject "..." --body "..." [--goal "..."] --json
ghostpost drafts [--status pending] --json                           # List drafts
ghostpost draft-approve <draft_id> --json                            # Send draft
ghostpost draft-reject <draft_id> --json                             # Reject draft
ghostpost generate-reply <thread_id> --json                          # AI-generate reply
```

#### AI Enrichment (3 commands)
```bash
ghostpost enrich --json                   # Run full enrichment (categorize, summarize, analyze)
ghostpost enrich-web <contact_id> --json  # Web-enrich a contact
ghostpost brief <thread_id> --json        # Get structured brief for thread
```

#### Goals (1 command, 5 subcommands)
```bash
ghostpost goal <thread_id> --set "..." --json                 # Set goal
ghostpost goal <thread_id> --criteria "..." --json            # Set acceptance criteria
ghostpost goal <thread_id> --check --json                     # LLM check if met
ghostpost goal <thread_id> --status met|abandoned --json      # Update status
ghostpost goal <thread_id> --clear --json                     # Clear goal
```

#### Playbooks (5 commands)
```bash
ghostpost playbooks --json                                    # List templates
ghostpost playbook <name> --json                              # Show content
ghostpost apply-playbook <thread_id> <name> --json            # Apply to thread
ghostpost playbook-create <name> --body "..." --json          # Create custom
ghostpost playbook-delete <name> --json                       # Delete custom
```

#### Security (3 commands with subcommands)
```bash
ghostpost quarantine list --json                     # List quarantined
ghostpost quarantine approve <event_id> --json       # Release
ghostpost quarantine dismiss <event_id> --json       # Dismiss
ghostpost blocklist list --json                      # View blocklist
ghostpost blocklist add <email> --json               # Add address
ghostpost blocklist remove <email> --json            # Remove address
ghostpost audit [--hours 24] [--limit 50] --json    # Agent action history
```

#### Settings (1 command, 3 subcommands)
```bash
ghostpost settings list --json            # All settings
ghostpost settings get <key> --json       # Single setting
ghostpost settings set <key> <value> --json
```

#### Research (Ghost Research skill)
```bash
ghostpost research run "Company" --goal "..." --identity ID --json
ghostpost research status <campaign_id> --json
ghostpost research list --json
ghostpost research batch <batch_id> --json
ghostpost research pause <batch_id> --json
ghostpost research resume <batch_id> --json
ghostpost research skip <campaign_id> --json
ghostpost research retry <campaign_id> --json
ghostpost research identities --json      # List configured identities
```

### JSON Output Format

All CLI commands when invoked with `--json` return:

**Success:**
```json
{
  "ok": true,
  "data": { ... }
}
```

**Connection Error:**
```json
{
  "ok": false,
  "error": "Connection refused",
  "code": "CONNECTION_ERROR",
  "retryable": true
}
```

**HTTP Error:**
```json
{
  "ok": false,
  "error": "...",
  "code": "HTTP_4XX|HTTP_5XX",
  "retryable": true|false,
  "status": 400|500|...
}
```

### Implementation Details

- **API Client:** `src/cli/api_client.py` (127 LOC) — httpx with JWT tokens
- **Formatters:** `src/cli/formatters.py` (71 LOC) — human + JSON output
- **JSON Mode:** `set_json_mode(enabled)` called by main.py when `--json` detected
- **Error Handling:** Connection errors and HTTP errors handled differently in JSON vs. human mode

---

## 4. REST API (FastAPI)

**Location:** `src/api/`  
**Entry Point:** `src/main.py` (FastAPI app)  
**Total Endpoints:** 73 endpoints across 19 route modules  
**Auth:** JWT token in `X-API-Key` header (from CLI: auto-generated from ADMIN_USERNAME + password)  

### API Route Modules

| Module | LOC | Endpoints | Purpose |
|--------|-----|-----------|---------|
| `health.py` | 35 | 1 | `GET /api/health` — DB + Redis readiness |
| `auth.py` | 59 | 2 | `POST /api/auth/login, /logout` — JWT cookie auth |
| `threads.py` | 325 | 8+ | List, fetch, update thread state/goal/auto-reply/follow-up |
| `emails.py` | 56 | 3 | Get single, list by thread, search |
| `contacts.py` | 69 | 2 | Get all, get by email address |
| `attachments.py` | 64 | 1 | GET /api/attachments/{id}/download |
| `drafts.py` | 65 | 5 | Create, list, approve, reject, get |
| `compose.py` | 119 | 1 | POST /api/compose — new email |
| `enrich.py` | 32 | 3 | Trigger enrichment, check status, get brief |
| `health.py` | 35 | 1 | Health check |
| `sync.py` | 25 | 2 | Trigger sync, get sync status |
| `stats.py` | 40 | 1 | Storage usage + counts |
| `goals.py` | — | 5 | Set, update, check, clear goals (via threads.py POST actions) |
| `security.py` | 104 | 7 | Quarantine list/approve/dismiss, blocklist CRUD |
| `audit.py` | — | 1 | `GET /api/audit` — action history |
| `playbooks.py` | 85 | 5 | List, get, apply, create, delete |
| `batch.py` | 44 | 2 | Send batch emails, get batch status |
| `notifications.py` | 33 | 2 | Get, update notification settings |
| `outcomes.py` | 68 | 2 | Get thread outcomes, create outcome |
| `settings.py` | 95 | 3 | List, get, update settings |
| `research.py` | 289 | 12 | Full research CRUD + batch + status + queue mgmt |
| `ws.py` | 50 | 1 | `WebSocket /api/ws` — real-time push (Redis pub/sub) |

### Key API Patterns

**Thread State Actions (via POST /api/threads/{id}/**...**):**
```
/reply                 # Send reply
/draft                 # Create draft
/state                 # Set thread state
/goal                  # Set/update goal
/acceptance-criteria   # Set acceptance criteria  
/goal-check           # LLM check if goal met
/goal-status          # Update goal status (in_progress/met/abandoned)
/goal-clear           # Clear goal
/auto-reply-mode      # Set auto-reply mode (off/draft/auto)
/follow-up            # Set follow-up interval
```

**Research Pipeline (via /api/research/*):**
```
POST /                                     # Create campaign
GET /<id>                                  # Get campaign status
GET /<id>/output/<phase_file.md>          # Read phase output
POST /<id>/phase/<phase>/retry            # Retry failed phase
POST /batch                                # Create batch
GET /batch/<batch_id>                      # Get batch status
POST /batch/<batch_id>/pause              # Pause batch
POST /batch/<batch_id>/resume             # Resume batch
POST /batch/<batch_id>/skip/<campaign_id> # Skip campaign
POST /batch/<batch_id>/retry/<campaign_id># Retry campaign
GET /identities                            # List identities
```

### Authentication

**For CLI:**
- Token auto-generated from `ADMIN_USERNAME` (from .env) + `ADMIN_PASSWORD` (hash)
- Sent as `X-API-Key` header

**For Frontend/External:**
- `POST /api/auth/login` with username/password
- Returns JWT in httpOnly cookie + response body

---

## 5. CONFIGURATION

**Location:** `config/`

### Ghost Research Configuration

**Defaults:** `config/ghost_research_defaults.md`
```yaml
default_language: "pt-PT"
default_email_tone: "direct-value"
default_auto_reply_mode: "draft-for-approval"
default_max_email_length: 150
default_follow_up_days: 3
# ... more
```

**Identities:** `config/identities/*.md`
- Each identity is a YAML frontmatter + markdown body
- Example: `capitao_consulting.md`
- Template: `_template.md`
- One identity locked per thread — all emails in thread use same identity

### Environment Variables

**Required (.env):**
```bash
ADMIN_USERNAME=athena
ADMIN_PASSWORD=<bcrypt hash of "ghostpost">
MINIMAX_API_KEY=<LLM API key>
SEARCH_API_KEY=<Serper API key for research>
GMAIL_OAUTH_TOKEN_FILE=token.json
REDIS_URL=redis://localhost:6379/1
DATABASE_URL=postgresql://contawise@localhost/ghostpost
```

---

## 6. INTEGRATION POINTS: HOW OPENCLAW USES GHOSTPOST

### Pattern 1: Read Context Files
```python
# OpenClaw startup
1. Read /home/athena/ghostpost/context/SYSTEM_BRIEF.md       # Orient
2. Read /home/athena/ghostpost/context/EMAIL_CONTEXT.md      # Threads list
3. Read /home/athena/ghostpost/context/threads/*.md          # Full thread details
4. Read /home/athena/ghostpost/context/RULES.md              # Style + blocklist
5. Read /home/athena/ghostpost/context/ACTIVE_GOALS.md       # Goals in flight
6. Read /home/athena/ghostpost/context/DRAFTS.md             # Review pending
7. Read /home/athena/ghostpost/context/SECURITY_ALERTS.md    # Security events
8. Read /home/athena/ghostpost/context/RESEARCH.md           # Research status
```

### Pattern 2: CLI Commands with --json
```bash
# Check health
ghostpost status --json | jq '.data'

# Get thread detail
ghostpost thread 42 --json | jq '.data'

# Create draft
ghostpost draft 42 --to someone@acme.com --subject "..." --body "..." --json

# Set goal
ghostpost goal 42 --set "Close deal by March 1" --json

# Run research
ghostpost research run "Acme Corp" --goal "Sell services" --identity capitao_consulting --json

# Check research status
ghostpost research status <campaign_id> --json
```

### Pattern 3: REST API Direct Calls
```python
import httpx

# From OpenClaw
client = httpx.Client(
    base_url="http://127.0.0.1:8000",
    headers={"X-API-Key": jwt_token}
)

# Read context
resp = client.get("/api/threads/42")
thread = resp.json()

# Create draft
resp = client.post("/api/drafts", json={
    "thread_id": 42,
    "to_addresses": ["someone@acme.com"],
    "subject": "...",
    "body": "..."
})
draft_id = resp.json()["id"]

# Approve draft
resp = client.post(f"/api/drafts/{draft_id}/approve")

# Start research
resp = client.post("/api/research", json={
    "company_name": "Acme Corp",
    "goal": "Sell AI consulting",
    "identity": "capitao_consulting",
    ...
})
campaign_id = resp.json()["id"]
```

### Pattern 4: File-Based Context Reading
```python
# Direct markdown file parsing (atomic guaranteed)
with open("/home/athena/ghostpost/context/SYSTEM_BRIEF.md") as f:
    brief_content = f.read()
    # Parse markdown table for threads needing attention
    
with open("/home/athena/ghostpost/context/threads/42.md") as f:
    thread_md = f.read()
    # Extract thread metadata, emails, analysis
```

---

## 7. PAIN POINTS & FRICTION

### 1. **Research Pipeline Coupling**
- Research campaigns are tied to threads + Gmail IDs
- If email send fails mid-phase, no graceful recovery (needs retry logic)
- **Gap:** No webhook for "research complete" — must poll status

### 2. **Goal Checking Complexity**
- Goal status requires LLM (`--check`), but no async job tracking
- OpenClaw must wait synchronously for LLM response
- **Gap:** No background goal-checking job; critical path on agent thread

### 3. **Multi-Step Workflows Fragmented**
- Compose → Draft → Approve is 3 separate CLI commands
- Research has internal queue but no parallel batch processing
- **Gap:** No CLI command for "compose and get approval" atomically

### 4. **Context File Parsing Burden**
- OpenClaw must regex parse markdown tables (SYSTEM_BRIEF, RESEARCH.md)
- Thread ID links in EMAIL_CONTEXT.md are relative paths
- **Gap:** No machine-readable API for "threads needing attention" (must parse markdown)

### 5. **Security Score Opacity**
- Threads have `security_score_avg` but no explanation
- EMAIL_CONTEXT shows "[LOW SECURITY SCORE]" but not which patterns triggered it
- **Gap:** No `GET /api/threads/{id}/security-details` endpoint

### 6. **Playbook Variable Substitution**
- Playbooks loaded as markdown, agent must do variable substitution
- Example: `{{recipient_name}}` requires manual replacement
- **Gap:** No `POST /api/playbooks/apply-with-vars` endpoint

### 7. **Follow-up Scheduling**
- Follows 3-day default but no intelligent snooze/reschedule
- No API to query "threads overdue for follow-up"
- **Gap:** No `GET /api/threads/overdue` endpoint

### 8. **WebSocket Real-Time Push**
- WebSocket exists (`/api/ws`) but only used by frontend
- OpenClaw can't subscribe to real-time email/draft events
- **Gap:** No documented WebSocket message schema for CLI/agent clients

### 9. **Batch Research Identity Lock**
- Identity picked at campaign start, immutable for all emails in thread
- Can't switch identity mid-thread (e.g., if sales person changes)
- **Gap:** No "reassign identity" operation

### 10. **Audit Log Querying**
- `GET /api/audit` returns raw action history
- No filtering by action_type, thread_id, or actor beyond time window
- **Gap:** Limited audit discoverability (e.g., "show all draft approvals")

---

## 8. ARCHITECTURE STRENGTHS

### Atomic Context Generation
✅ All context files use temp+rename pattern — readers never see partial files

### Security-First Design
✅ All untrusted email content wrapped in isolation markers  
✅ 6-layer injection defense (sanitizer, detector, commitment, anomaly, safeguards, audit)

### Schema Versioning
✅ Every context file has `schema_version` on line 2 for graceful evolution

### --json Everywhere
✅ All 43 CLI commands support structured JSON output  
✅ Errors differentiate CONNECTION_ERROR vs HTTP_4XX vs HTTP_5XX with retryable flag

### Skills Framework Ready
✅ Ghost Research SKILL.md is standalone, reusable template  
✅ Clear separation: skill definition (SKILL.md) + backend (src/research/) + API (routes/research.py) + CLI (cli/research.py)

### Hierarchical Context Reading
✅ SYSTEM_BRIEF → EMAIL_CONTEXT → (per-thread files) follows agent's cognitive flow  
✅ Drafts, goals, alerts are all accessible from context files without API calls

---

## 9. RECOMMENDED NEXT IMPROVEMENTS

### Priority 1 (High Value, Low Effort)
1. **`GET /api/threads/attention`** — Return threads needing action (priority=high/critical OR overdue follow-up), parsed from SYSTEM_BRIEF logic
2. **`POST /api/compose-and-draft`** — Atomic compose + draft creation without approval
3. **`GET /api/threads/{id}/security-details`** — Explain why security_score_avg is low (which patterns triggered it)
4. **`GET /api/research/status?batch_id={id}`** — Dedicated batch status endpoint instead of nested route

### Priority 2 (Important, Moderate Effort)
5. **Async goal checking** — Background job for `goal --check`, expose job ID + polling endpoint
6. **`GET /api/threads/overdue`** — Threads past next_follow_up_date with filter options
7. **WebSocket schema documentation** — Publish message types for agent subscriptions
8. **Batch research parallelization** — Config option for N parallel campaigns instead of sequential

### Priority 3 (Nice-to-Have)
9. **Playbook variable substitution API** — `POST /api/playbooks/{name}/apply-vars`
10. **Audit filtering** — `GET /api/audit?action_type=draft_approved&thread_id=42`

---

## 10. SKILLS FRAMEWORK TEMPLATE

For creating new skills (beyond Ghost Research):

```yaml
---
name: [skill-name]
description: Short description
user-invocable: true
---

# [Skill Name]

## Overview
What problem does this solve?

## Architecture
- **Backend:** src/[skill]/
- **DB Models:** [models in src/db/models.py]
- **API:** /api/[skill]/* endpoints
- **CLI:** ghostpost [skill] commands
- **Config:** config/[skill]_*.md

## How to Use
CLI examples and/or API examples

## Integration Points
- What context files does it read/write?
- Does it trigger enrichment?
- Does it interact with Gmail?

## Configuration
Environment variables, config files, defaults

## Important Rules
Constraints and guidelines for safe operation
```

---

## 11. VERIFICATION CHECKLIST

For OpenClaw integration testing:

- [ ] All 43 CLI commands work with `--json` flag
- [ ] Context files exist and are readable after sync
- [ ] SYSTEM_BRIEF updates on every sync
- [ ] Thread files are moved from threads/ to threads/archive/ when state=ARCHIVED
- [ ] UNTRUSTED markers appear in thread files for received emails
- [ ] Draft creation doesn't send until approval
- [ ] Goal checking waits for LLM response
- [ ] Research campaigns persist output to research/[company_slug]/
- [ ] Blocklist prevents replies to blocked addresses
- [ ] Security score < 50 prevents auto-replies
- [ ] Atomic writes mean no partial context files even if process crashes mid-write

