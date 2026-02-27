# GhostPost Complete Capability Inventory

**Last Updated:** 2026-02-26  
**Version:** Phase 7 Complete (Agent Optimization + Research)

This inventory lists ALL capabilities OpenClaw skills should expose. Organized by functional area.

---

## 1. EMAIL READING & SEARCHING

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost threads` | `--state`, `--limit`, `--table`, `--json` | List all threads with pagination & filtering |
| `ghostpost thread <id>` | `--json` | Get single thread with all emails + metadata |
| `ghostpost email <id>` | `--json` | Get single email details |
| `ghostpost search <query>` | `--limit`, `--table`, `--json` | Full-text search (subject/body/sender) |
| `ghostpost brief <id>` | `--json` | Get AI-generated structured brief for thread |
| `ghostpost notes <id>` | `--text`, `--json` | View/set notes on a thread |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/threads` | List threads (page, page_size, state, q filters) |
| GET | `/api/threads/{id}` | Thread detail with all emails |
| GET | `/api/threads/{id}/brief` | Markdown brief (agent consumption) |
| GET | `/api/emails/search` | Search emails (q, page_size) |
| GET | `/api/emails/{id}` | Single email details |

### Engine Functions
- **brief.py:** `generate_brief(thread_id)` → Markdown narrative + agent instructions
- **context_writer.py:** `write_email_context()` → EMAIL_CONTEXT.md with thread summaries

---

## 2. SENDING EMAILS & COMPOSING

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost compose` | `--to`, `--subject`, `--body`, `--cc`, `--goal`, `--acceptance-criteria`, `--playbook`, `--auto-reply`, `--follow-up-days`, `--priority`, `--category`, `--notes`, `--json` | Send new email with full agent context |
| `ghostpost reply <id>` | `--body`, `--cc`, `--draft`, `--json` | Reply to thread (or save as draft with `--draft`) |
| `ghostpost generate-reply <id>` | `--instructions`, `--style`, `--draft`, `--json` | AI-generate reply (optionally create draft) |
| `ghostpost draft <id>` | `--to`, `--subject`, `--body`, `--json` | Create email draft (no send) |
| `ghostpost drafts` | `--status`, `--json` | List pending drafts |
| `ghostpost draft-approve <id>` | `--json` | Approve & send draft (runs safeguards) |
| `ghostpost draft-reject <id>` | `--json` | Reject draft (no send) |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| POST | `/api/compose` | Send new email (batches >20 recipients automatically) |
| POST | `/api/threads/{id}/reply` | Reply (with draft=true query param for draft mode) |
| POST | `/api/threads/{id}/draft` | Create email draft |
| POST | `/api/threads/{id}/generate-reply` | AI-generate reply (instructions, style, create_draft) |
| GET | `/api/drafts` | List drafts (status filter) |
| POST | `/api/drafts/{id}/approve` | Approve draft (run safeguards, send) |
| POST | `/api/drafts/{id}/reject` | Reject draft |

### Engine Functions
- **composer.py:** `generate_reply(thread_id, instructions, style)` → LLM-generated reply body
- **send.py:** `send_reply()`, `send_new()`, `create_draft()` → Gmail operations with MIME threading
- **state_machine.py:** Auto-transitions thread state on send (NEW→ACTIVE, ACTIVE→WAITING_REPLY, etc.)
- **safeguards.py:** Pre-send checks (blocklist, rate limiting, sensitive topics, commitment detection)

---

## 3. THREAD STATE & LIFECYCLE

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost state <id> <NEW\|ACTIVE\|WAITING_REPLY\|FOLLOW_UP\|GOAL_MET\|ARCHIVED>` | `--reason`, `--json` | Change thread state (with audit trail) |
| `ghostpost toggle <id>` | `--mode off\|draft\|auto`, `--json` | Set auto-reply mode |
| `ghostpost followup <id>` | `--days`, `--json` | Set follow-up check-in interval |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| PUT | `/api/threads/{id}/state` | Transition state with reason |
| PUT | `/api/threads/{id}/auto-reply` | Set auto-reply mode (off/draft/auto) |
| PUT | `/api/threads/{id}/follow-up` | Set follow-up days |
| PUT | `/api/threads/{id}/notes` | Set/update thread notes |

### Engine Functions
- **state_machine.py:** `transition(thread_id, new_state, reason, actor)` → State changes + audit log
- **followup.py:** Scheduler checks overdue threads, triggers follow-up events

### Valid States
```
NEW → ACTIVE → WAITING_REPLY → FOLLOW_UP → GOAL_MET → ARCHIVED
```

---

## 4. GOALS & ACCEPTANCE CRITERIA

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost goal <id>` | `--set`, `--criteria`, `--status`, `--check`, `--clear`, `--json` | Manage thread goals |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| PUT | `/api/threads/{id}/goal` | Set goal + acceptance criteria |
| PUT | `/api/threads/{id}/goal/status` | Update goal status (in_progress/met/abandoned) |
| POST | `/api/threads/{id}/goal/check` | LLM check if goal is met |
| DELETE | `/api/threads/{id}/goal` | Clear goal |

### Engine Functions
- **goals.py:** `set_goal()`, `check_goal_met()`, `clear_goal()` → Goal lifecycle
- **brief.py:** Generates "## Agent Instructions" with goal-check guidance

---

## 5. PLAYBOOKS

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost playbooks` | `--json` | List all available playbooks |
| `ghostpost playbook <name>` | `--json` | Show full playbook markdown content |
| `ghostpost apply-playbook <id> <name>` | `--json` | Apply playbook template to thread |
| `ghostpost playbook-create <name>` | `--body`, `--json` | Create new playbook markdown |
| `ghostpost playbook-delete <name>` | `--json` | Delete a playbook |
| `ghostpost playbook-update <name>` | `--body`, `--json` | Update playbook markdown |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/playbooks` | List playbooks |
| GET | `/api/playbooks/{name}` | Get playbook content (text/plain) |
| POST | `/api/playbooks/apply/{id}/{name}` | Apply playbook to thread |
| POST | `/api/playbooks` | Create new playbook |
| PUT | `/api/playbooks/{name}` | Update playbook |
| DELETE | `/api/playbooks/{name}` | Delete playbook |

### Built-In Playbooks
- `schedule-meeting` — Negotiate meeting time
- `negotiate-price` — Price negotiation with fallback
- `follow-up-generic` — Generic follow-up template
- `close-deal` — Move toward signed commitment

---

## 6. SECURITY & SAFEGUARDS (6-Layer Defense)

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost quarantine list` | `--json` | List quarantined/suspicious emails |
| `ghostpost quarantine approve <id>` | `--json` | Release from quarantine + mark safe |
| `ghostpost quarantine dismiss <id>` | `--json` | Dismiss without releasing |
| `ghostpost blocklist list` | `--json` | Show blocklist |
| `ghostpost blocklist add <email>` | `--json` | Block sender |
| `ghostpost blocklist remove <email>` | `--json` | Unblock sender |
| `ghostpost security-events` | `--pending-only`, `--limit`, `--json` | List security incidents |
| `ghostpost audit` | `--hours`, `--limit`, `--json` | Agent action audit trail |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/security/events` | List security events |
| GET | `/api/security/quarantine` | List quarantined items |
| POST | `/api/security/quarantine/{id}/approve` | Release from quarantine |
| POST | `/api/security/quarantine/{id}/dismiss` | Dismiss quarantine event |
| GET | `/api/security/blocklist` | Get blocklist |
| POST | `/api/security/blocklist` | Add email to blocklist |
| DELETE | `/api/security/blocklist` | Remove from blocklist |
| GET | `/api/audit` | Agent action audit log |

### Security Layers
1. **Sanitizer (sanitizer.py)** — HTML/script stripping, input validation
2. **Content Isolation** — Email bodies are untrusted; never eval/execute
3. **Injection Detector (injection_detector.py)** — 18 prompt injection patterns scanned
4. **Commitment Detector (commitment_detector.py)** — Flags binding promises
5. **Anomaly Detector (anomaly_detector.py)** — Rate checking + new recipient flagging
6. **Safeguards (safeguards.py)** — Master pre-send check (runs all 6 layers)

### Engine Functions
- **safeguards.py:** `check_send_allowed(to, body)` → Master safeguard orchestrator
- **injection_detector.py:** `detect_injections(text)` → Returns injection patterns found
- **commitment_detector.py:** `detect_commitments(text)` → Flags binding language
- **audit.py:** `log_action()`, `log_security_event()` → Complete audit trail
- **anomaly_detector.py:** Rate limits + new recipient detection

---

## 7. TRIAGE & PRIORITIZATION

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost triage` | `--limit`, `--json` | Single entry point: inbox snapshot + prioritized actions |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/triage/` | Triage snapshot (summary + actions list) |

### Triage Snapshot Includes
```json
{
  "summary": {
    "total_threads": N,
    "unread": N,
    "new_threads": N,
    "pending_drafts": N,
    "overdue_threads": N,
    "security_incidents": N,
    "by_state": {"NEW": N, "ACTIVE": N, ...}
  },
  "actions": [
    {
      "priority": "critical|high|medium|low",
      "action": "approve_draft|follow_up|review_security|...",
      "reason": "...",
      "command": "exact CLI command to run"
    }
  ]
}
```

### Engine Functions
- **triage.py:** `get_triage_data(limit)` → Prioritized action list for agent

---

## 8. AI ENRICHMENT & ANALYSIS

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost enrich` | `--json` | Run all AI enrichment jobs (categorize, summarize, analyze) |
| `ghostpost enrich-web <id>` | `--json` | LLM infer company/role from contact name + email domain |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| POST | `/api/enrich` | Trigger enrichment batch |
| GET | `/api/enrich/status` | Enrichment job status |
| POST | `/api/contacts/{id}/enrich-web` | Web-enrich a contact |

### Engine Functions
- **enrichment.py:** `run_enrichment()` → Orchestrates all AI jobs
- **categorizer.py:** LLM assigns freeform category to thread
- **summarizer.py:** LLM generates thread summary
- **analyzer.py:** Sentiment, urgency, action_required per email + priority per thread
- **contacts.py:** Enriches contact profiles (name, email → company, title, relationship)
- **context_writer.py:** Writes SYSTEM_BRIEF.md, EMAIL_CONTEXT.md, CONTACTS.md, etc.

### Requires LLM
- Set `MINIMAX_API_KEY` in .env (or use OpenClaw gateway)
- Security scoring works offline; AI features require LLM

---

## 9. CONTACTS & ENRICHMENT

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost contacts` | `--limit`, `--search`, `--json` | List contacts with pagination |
| `ghostpost contact <id>` | `--json` | Contact detail (name, email, company, title, notes) |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/contacts` | List contacts (page_size, q) |
| GET | `/api/contacts/{id}` | Contact detail |
| POST | `/api/contacts/{id}/enrich-web` | LLM inference for profile |

---

## 10. RESEARCH PIPELINE (Ghost Research)

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost research run <company>` | `--goal`, `--identity`, `--language`, `--country`, `--industry`, `--contact-name`, `--contact-email`, `--contact-role`, `--tone`, `--mode`, `--watch/--no-watch`, `--json` | Start research (verbose watch on by default) |
| `ghostpost research status <id>` | `--watch`, `--json` | Campaign status + verbose log history |
| `ghostpost research list` | `--status`, `--json` | List campaigns |
| `ghostpost research batch <batch_id>` | `--json` | Get batch status |
| `ghostpost research pause <id>` | `--json` | Pause batch |
| `ghostpost research resume <id>` | `--json` | Resume batch |
| `ghostpost research skip <id>` | `--json` | Skip to next company |
| `ghostpost research retry <id>` | `--json` | Retry failed campaign |
| `ghostpost research identities` | `--json` | List available sender identities |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| POST | `/api/research/` | Start campaign (ResearchRequest) |
| POST | `/api/research/batch` | Start batch (multiple companies) |
| GET | `/api/research/` | List campaigns (status filter) |
| GET | `/api/research/{id}` | Campaign detail |
| GET | `/api/research/{id}/output/{filename}` | Download research markdown (00-06) |
| GET | `/api/research/identities` | List sender identities |
| GET | `/api/research/batches` | List batches |
| GET | `/api/research/batch/{id}` | Batch detail |
| POST | `/api/research/batch/{id}/pause` | Pause batch |
| POST | `/api/research/batch/{id}/resume` | Resume batch |
| POST | `/api/research/{id}/skip` | Skip campaign |
| POST | `/api/research/{id}/retry` | Retry campaign |

### Research Phases
1. **Input Collection** — Parse goals, validate contact info
2. **Deep Research** — Serper API + web scraping
3. **Opportunity Analysis** — Identify pain points + fit
4. **Contacts Search** — Find best contact email
5. **Person Research** — Deep profile on named contact (conditional, when contact_name provided)
6. **Peer Intelligence** — Company size, funding, growth
7. **Value Proposition** — Build personalized value prop
8. **Email Composition** — Generate outreach email (markdown)

### Verbose Logging (Always On)
- `research run` streams real-time verbose output by default (`--watch` is on)
- Each phase emits timestamped log entries: web search counts, LLM calls, file writes, errors
- Format: `[HH:MM:SS] [P2] Executing 14 web searches across 4 rounds`
- Verbose log persists in DB at `research_data.verbose_log` (array of `{ts, phase, msg}`)
- `research status` always displays full verbose log history
- Use `--no-watch` to skip live streaming (campaign still runs in background)

### Outputs
- Markdown files in `research/[company_slug]/` (00-input through 05-email)
- Persisted permanently; reusable for follow-ups
- Auto-creates thread on email send

---

## 11. OUTCOMES & KNOWLEDGE EXTRACTION

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost outcomes list` | `--limit`, `--json` | List completed thread outcomes |
| `ghostpost outcomes get <id>` | `--json` | Outcome detail for a thread |
| `ghostpost outcomes extract <id>` | `--json` | Trigger knowledge extraction |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/outcomes` | List outcomes |
| GET | `/api/outcomes/{id}` | Outcome detail |
| POST | `/api/threads/{id}/extract` | Extract outcome from thread |

### Engine Functions
- **knowledge.py:** `extract_outcome()` → Knowledge extraction from completed threads

---

## 12. BATCH & BULK OPERATIONS

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost batch list` | `--json` | List enrichment batch jobs |
| `ghostpost batch detail <id>` | `--json` | Batch job detail |
| `ghostpost batch cancel <id>` | `--json` | Cancel running batch |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/batch` | List batch jobs |
| GET | `/api/batch/{id}` | Batch job detail |
| POST | `/api/batch/{id}/cancel` | Cancel batch |

### Engine Functions
- **batch.py:** `create_batch_job()` → Clusters >20 recipients, 1 email per cluster per hour

---

## 13. SETTINGS & CONFIGURATION

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost settings list` | `--json` | All settings |
| `ghostpost settings get <key>` | `--json` | Single setting |
| `ghostpost settings set <key> <value>` | `--json` | Update setting |
| `ghostpost settings delete <key>` | `--json` | Reset to default |
| `ghostpost settings bulk <k=v> [k=v]` | `--json` | Bulk update |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/settings` | All settings |
| GET | `/api/settings/{key}` | Single setting |
| PUT | `/api/settings/{key}` | Update setting |
| DELETE | `/api/settings/{key}` | Reset setting |
| PUT | `/api/settings/bulk` | Bulk update |

### Key Settings
- `reply_style` — professional|casual|formal|custom
- `reply_style_custom` — Custom style prompt
- `never_auto_reply` — Comma-separated emails
- `rate_limit_per_hour` — Max emails per hour
- `sensitive_topics` — Topics triggering review

---

## 14. NOTIFICATIONS & ALERTS

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost alerts` | `--json` | Active notification alerts |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/notifications/alerts` | Active alerts |

### Context Files (Auto-Updated)
| File | Purpose |
|------|---------|
| `ALERTS.md` | Follow-up reminders, stale threads, system notifications |
| `SECURITY_ALERTS.md` | Quarantined emails, injection attempts |

---

## 15. ATTACHMENTS

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost attachment <id>` | `--output`, `--json` | Download attachment |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/attachments/{id}/download` | Download attachment (binary) |

---

## 16. SYSTEM & HEALTH

### CLI Commands
| Command | Flags | What It Does |
|---------|-------|-------------|
| `ghostpost health` | `--json` | API health (db, redis) |
| `ghostpost status` | `--json` | Full status (health + inbox snapshot + SYSTEM_BRIEF.md) |
| `ghostpost stats` | `--json` | Storage usage + counts |
| `ghostpost sync` | `--json` | Trigger Gmail sync |

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| GET | `/api/health` | Health check (db, redis) |
| GET | `/api/stats` | Inbox statistics |
| POST | `/api/sync` | Trigger Gmail sync |
| GET | `/api/sync/status` | Sync status |

### Engine Functions
- **context_writer.py:** `write_all()` → Regenerates all context files (SYSTEM_BRIEF, EMAIL_CONTEXT, CONTACTS, etc.)

---

## 17. AUTHENTICATION

### API Routes
| Method | Endpoint | What It Does |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login with password → JWT token |
| POST | `/api/auth/logout` | Logout (clear token) |
| GET | `/api/auth/me` | Current user info |

---

## 18. CONTEXT FILES (Living Agent Documentation)

All live at `/home/athena/ghostpost/context/`, auto-updated on sync.

| File | Schema | What It Provides | Updated On |
|------|--------|-----------------|------------|
| `SYSTEM_BRIEF.md` | YAML frontmatter | Health, inbox counts, priorities, pending goals | Every sync |
| `EMAIL_CONTEXT.md` | YAML frontmatter | Active threads: sender, state, summary, score | Every sync |
| `CONTACTS.md` | YAML frontmatter | Enriched profiles: name, email, company, title, tone | After interaction |
| `RULES.md` | YAML frontmatter | Reply style, blocklists, auto-reply rules, playbook index | User changes |
| `ACTIVE_GOALS.md` | YAML frontmatter | All threads with active goals + acceptance criteria | Goal event |
| `DRAFTS.md` | YAML frontmatter | Pending drafts awaiting approval | Draft event |
| `SECURITY_ALERTS.md` | YAML frontmatter | Quarantined emails, injection attempts, anomalies | Security event |
| `ALERTS.md` | YAML frontmatter | Follow-up reminders, stale threads, notifications | Every sync |
| `RESEARCH.md` | YAML frontmatter | Active research campaigns, recent completions | Research event |
| `COMPLETED_OUTCOMES.md` | YAML frontmatter | Completed thread outcomes + learnings | Outcome event |
| `CHANGELOG.md` | Plain markdown | Event log (prepend, max 100 entries) — for heartbeat detection | Major event |
| `thread/<id>.md` | YAML frontmatter | Per-thread detail: emails, state, goal, actions | After any change |

### YAML Frontmatter Format
```yaml
---
schema_version: 1
type: system_brief|email_context|contacts|rules|...
updated_at: 2026-02-26T20:57:00Z
count: N
---
```

---

## 19. ENGINE MODULES (Internal Functions)

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| **brief.py** | `generate_brief(thread_id)` | Markdown narrative + agent instructions |
| **categorizer.py** | LLM assigns freeform category | Thread classification |
| **summarizer.py** | LLM generates summary | Thread summary on each email |
| **analyzer.py** | sentiment, urgency, action_required | Email analysis + thread priority |
| **contacts.py** | Enriches contact profiles | Contact enrichment from email history |
| **composer.py** | `generate_reply()` | AI reply generation with style |
| **state_machine.py** | `transition()` | Thread state transitions + audit |
| **goals.py** | `set_goal()`, `check_goal_met()` | Goal lifecycle |
| **followup.py** | Scheduler job | Overdue follow-up detection |
| **batch.py** | `create_batch_job()` | Batch clustering for >20 recipients |
| **enrichment.py** | `run_enrichment()` | Orchestrates all AI jobs |
| **context_writer.py** | `write_all()` | Generates all context files |
| **triage.py** | `get_triage_data()` | Prioritized action list |
| **knowledge.py** | `extract_outcome()` | Knowledge extraction |
| **notifications.py** | Notification filtering | Alert generation |
| **llm.py** | `complete()` | OpenClaw gateway LLM calls |
| **security.py** | `calculate_score()` | Rule-based security 0-100 |

---

## 20. GMAIL MODULES (Sync & Send)

| Module | Key Functions | Purpose |
|--------|---------------|---------|
| **auth.py** | OAuth2 flow | Gmail credential management |
| **client.py** | GmailClient wrapper | Async Gmail API calls |
| **sync.py** | `SyncEngine.full_sync()`, `.incremental_sync()` | Mirror Gmail to DB |
| **parser.py** | Parse Gmail API responses | Convert Gmail API → DB models |
| **send.py** | `send_reply()`, `send_new()`, `create_draft()` | MIME message building + sending |
| **scheduler.py** | APScheduler jobs | 30-min heartbeat sync |

---

## 21. SECURITY MODULES

| Module | Layers | Checks |
|--------|--------|--------|
| **sanitizer.py** | 1-2 | HTML stripping, script removal, input validation |
| **injection_detector.py** | 3 | 18 prompt injection patterns |
| **commitment_detector.py** | 4 | Binding promise detection |
| **anomaly_detector.py** | 5 | Rate limiting, new recipient flagging |
| **safeguards.py** | Master | Blocklist, never-auto-reply, sensitive topics, all 6 layers |
| **audit.py** | Audit | Action logging, security event recording |

---

## 22. RESEARCH MODULES

| Module | Purpose |
|--------|---------|
| **pipeline.py** | `create_campaign()`, `run_pipeline()` — 8-phase pipeline |
| **queue.py** | Batch management (create, pause, resume, skip, retry) |
| **identities.py** | Sender identity management (YAML files) |
| **web_research.py** | Serper API search + httpx page fetch |
| **input_collector.py** | Goal/contact parsing |
| **researcher.py** | Phase 2 (deep research) |
| **opportunity.py** | Phase 3 (opportunity analysis) |
| **peer_intel.py** | Phase 4 (company intelligence) |
| **value_plan.py** | Phase 5 (personalized value prop) |
| **email_writer.py** | Phase 6 (email generation) |

---

## QUICK REFERENCE: Command Patterns

### All Commands Support `--json`
Returns structured envelope:
```json
{"ok": true, "data": {...}}
or
{"ok": false, "error": "message", "code": "ERROR_CODE", "retryable": true/false}
```

### Compound Operations
- `ghostpost reply <id> --draft` — Create draft instead of send
- `ghostpost generate-reply <id> --draft` — Generate + auto-create draft
- `ghostpost reply <id> --body "..." --draft` — Combined

### Safety Principles
1. **Drafts first** — Use `--draft` flag to create draft for approval
2. **Blocklist enforcement** — All sends check blocklist
3. **Safeguard checks** — All outgoing emails run 6-layer security
4. **Audit trail** — Every action logged with actor + timestamp
5. **State transitions** — Auto-happen on send/receive

---

## SUMMARY FOR SKILLS

OpenClaw skills should expose these capability groups:

1. **Email Reading** (threads, emails, search, brief)
2. **Sending** (compose, reply, generate-reply, drafts)
3. **Thread Management** (state, goals, follow-up, notes)
4. **Playbooks** (list, view, apply)
5. **Security** (quarantine, blocklist, audit, events)
6. **Triage** (prioritized actions)
7. **Enrichment** (AI analysis, contact enrichment)
8. **Research** (campaigns, batches, identities)
9. **Outcomes** (extraction, learning)
10. **Settings** (configuration)
11. **System** (health, sync, stats)

**Reference:** All 12 skills in `.claude/skills/ghostpost-*/SKILL.md`
