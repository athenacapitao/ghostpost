# GhostPost API Reference

Base URL: `http://127.0.0.1:8000`

All endpoints except `/api/health` and `/api/auth/login` require authentication via:
- `X-API-Key: <JWT>` header, or
- `access_token` httpOnly cookie

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | No | Liveness check. Returns `{status, db, redis}` |

---

## Auth

| Method | Path | Auth | Description | Body |
|--------|------|------|-------------|------|
| POST | `/api/auth/login` | No | Login, sets cookie | `{username, password}` |
| POST | `/api/auth/logout` | No | Clears cookie | — |
| GET | `/api/auth/me` | Yes | Returns current username | — |

---

## Threads

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/threads` | Yes | List threads (paginated) | `page`, `page_size`, `state`, `q` (search) |
| GET | `/api/threads/{id}` | Yes | Thread detail with emails | — |
| GET | `/api/threads/{id}/brief` | Yes | Markdown brief (plaintext) | — |
| POST | `/api/threads/{id}/reply` | Yes | Send reply or save as draft | Body: `{body, cc?, bcc?}`. Query: `draft=true` to skip send |
| POST | `/api/threads/{id}/draft` | Yes | Create draft with explicit to/subject | Body: `{to, subject, body, cc?, bcc?}` |
| POST | `/api/threads/{id}/generate-reply` | Yes | LLM-generated reply | Query: `instructions`, `style`, `create_draft=true` |
| PUT | `/api/threads/{id}/state` | Yes | Manual state transition | Body: `{state, reason?}` |
| PUT | `/api/threads/{id}/auto-reply` | Yes | Set auto-reply mode | Body: `{mode}` — `off`, `draft`, `auto` |
| PUT | `/api/threads/{id}/follow-up` | Yes | Set follow-up window | Body: `{days}` |
| PUT | `/api/threads/{id}/notes` | Yes | Update thread notes | Body: `{notes}` |
| PUT | `/api/threads/{id}/goal` | Yes | Set thread goal | Body: `{goal, acceptance_criteria}` |
| DELETE | `/api/threads/{id}/goal` | Yes | Remove thread goal | — |
| PUT | `/api/threads/{id}/goal/status` | Yes | Update goal status | Body: `{status}` |
| POST | `/api/threads/{id}/goal/check` | Yes | LLM goal-met check | — |
| POST | `/api/threads/{id}/extract` | Yes | Trigger knowledge extraction | Thread must be GOAL_MET or ARCHIVED |

---

## Emails

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/emails/search` | Yes | Full-text search | `q` (required), `page`, `page_size` |
| GET | `/api/emails/{id}` | Yes | Single email detail | — |

---

## Contacts

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/contacts` | Yes | List contacts (paginated) | `page`, `page_size`, `q` |
| GET | `/api/contacts/{id}` | Yes | Single contact detail | — |
| POST | `/api/contacts/{id}/enrich-web` | Yes | Web enrichment via LLM | — |

---

## Compose

| Method | Path | Auth | Description | Body |
|--------|------|------|-------------|------|
| POST | `/api/compose` | Yes | Send new email. Auto-batches when >20 recipients | `{to, subject, body, cc?, bcc?, goal?, acceptance_criteria?, playbook?, auto_reply_mode?, follow_up_days?, priority?, category?, notes?}` |

---

## Drafts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/drafts` | Yes | List drafts. Query: `status` (default `pending`) |
| POST | `/api/drafts/{id}/approve` | Yes | Approve draft — runs safeguards then sends |
| POST | `/api/drafts/{id}/reject` | Yes | Reject draft |

---

## Sync

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/sync` | Yes | Trigger incremental Gmail sync (background) |
| GET | `/api/sync/status` | Yes | Current sync status and last run time |

---

## Enrichment

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/enrich` | Yes | Trigger full enrichment pipeline (background) |
| GET | `/api/enrich/status` | Yes | Whether enrichment is running and LLM is available |

---

## Security

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/security/events` | Yes | List security events | `pending_only=true`, `limit` |
| GET | `/api/security/quarantine` | Yes | Pending quarantine events only | — |
| POST | `/api/security/quarantine/{id}/approve` | Yes | Mark quarantine as safe | — |
| POST | `/api/security/quarantine/{id}/dismiss` | Yes | Dismiss without approving | — |
| GET | `/api/security/blocklist` | Yes | Get blocklist | — |
| POST | `/api/security/blocklist` | Yes | Add to blocklist | Body: `{email}` |
| DELETE | `/api/security/blocklist` | Yes | Remove from blocklist | Body: `{email}` |

---

## Audit

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/audit` | Yes | Recent audit log entries | `hours` (1-168, default 24), `limit` (max 500) |

---

## Playbooks

| Method | Path | Auth | Description | Body/Params |
|--------|------|------|-------------|------------|
| GET | `/api/playbooks` | Yes | List all playbooks | — |
| GET | `/api/playbooks/{name}` | Yes | Get playbook content (plaintext) | — |
| POST | `/api/playbooks` | Yes | Create playbook | Query: `name`. Body: `{content}` |
| PUT | `/api/playbooks/{name}` | Yes | Update playbook | Body: `{content}` |
| DELETE | `/api/playbooks/{name}` | Yes | Delete playbook | — |
| POST | `/api/playbooks/apply/{thread_id}/{name}` | Yes | Apply playbook to thread | — |

---

## Settings

| Method | Path | Auth | Description | Body |
|--------|------|------|-------------|------|
| GET | `/api/settings` | Yes | All settings with defaults | — |
| GET | `/api/settings/{key}` | Yes | Single setting | — |
| PUT | `/api/settings/{key}` | Yes | Set single setting | `{value}` |
| PUT | `/api/settings/bulk` | Yes | Set multiple settings | `{settings: {key: value}}` |
| DELETE | `/api/settings/{key}` | Yes | Reset to default | — |

**Known setting keys:** `reply_style`, `reply_style_custom`, `default_follow_up_days`, `commitment_threshold`, `notification_new_email`, `notification_goal_met`, `notification_security_alert`, `notification_draft_ready`, `notification_stale_thread`

---

## Notifications

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/notifications/alerts` | Yes | Parsed alerts from `context/ALERTS.md` |

---

## Outcomes

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/outcomes` | Yes | All extracted outcomes | `limit`, `offset` |
| GET | `/api/outcomes/{thread_id}` | Yes | Outcome for a specific thread | — |

---

## Stats

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/stats` | Yes | Counts: threads, emails, contacts, attachments, unread, DB size MB |

---

## Attachments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/attachments/{id}/download` | Yes | Download attachment (lazy fetch from Gmail on first request) |

---

## Batch (Compose)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/batch` | Yes | List batch jobs |
| GET | `/api/batch/{id}` | Yes | Batch job detail with items |
| POST | `/api/batch/{id}/cancel` | Yes | Cancel pending/in-progress batch |

---

## Triage

| Method | Path | Auth | Description | Key Params |
|--------|------|------|-------------|------------|
| GET | `/api/triage/` | Yes | Prioritized action list for agent decision-making | `limit` (1-50, default 10) |

---

## Research (Ghost Research)

| Method | Path | Auth | Description | Body/Params |
|--------|------|------|-------------|------------|
| POST | `/api/research/` | Yes | Start single company research campaign | `{company_name, goal, identity?, language?, country?, industry?, contact_name?, contact_email?, contact_role?, email_tone?, auto_reply_mode?, max_auto_replies?}` |
| GET | `/api/research/` | Yes | List campaigns | `status`, `batch_id`, `page`, `page_size` |
| GET | `/api/research/identities` | Yes | List sender identities | — |
| GET | `/api/research/batches` | Yes | List research batches | `page`, `page_size` |
| POST | `/api/research/batch` | Yes | Start batch of campaigns | `{name, companies: [...], defaults?: {...}}` |
| GET | `/api/research/batch/{id}` | Yes | Batch status with all campaigns | — |
| POST | `/api/research/batch/{id}/pause` | Yes | Pause running batch | — |
| POST | `/api/research/batch/{id}/resume` | Yes | Resume paused batch | — |
| GET | `/api/research/{campaign_id}` | Yes | Campaign detail (includes verbose log) | — |
| GET | `/api/research/{campaign_id}/output/{filename}` | Yes | Research output file content | `filename`: `00_input.md`, `01_company_dossier.md`, `02_opportunity_analysis.md`, `03_contacts_search.md`, `04b_person_profile.md` (conditional), `04_peer_intelligence.md`, `05_value_proposition_plan.md`, `06_email_draft.md` |
| POST | `/api/research/{campaign_id}/skip` | Yes | Skip queued campaign | — |
| POST | `/api/research/{campaign_id}/retry` | Yes | Retry failed campaign | — |

**Verbose Log:** Campaign detail (`GET /api/research/{id}`) includes `research_data.verbose_log` — an array of `{ts, phase, msg}` entries streamed in real time during pipeline execution. Poll this endpoint to monitor progress. The CLI `ghostpost research run` does this automatically with `--watch` (on by default).

---

## WebSocket

| Path | Auth | Description |
|------|------|-------------|
| `ws://host/api/ws?token=<JWT>` | JWT query param | Real-time events via Redis pub/sub |

Event types pushed over WebSocket: `audit`, `security_alert`, `state_changed`, `follow_up_triggered`, and any custom published event.
