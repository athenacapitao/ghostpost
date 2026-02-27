# Phase 3 — Agent Actions Implementation Plan

## Overview
Agent can reply, compose, manage threads with goals, state machine, follow-ups, and playbooks.

## 9 Sequential Steps

---

### Step 1: Gmail Send + Reply + Draft
**New file:** `src/gmail/send.py`

- `send_reply(thread_id, body, cc=None, bcc=None)` — reply to existing thread (sets In-Reply-To, References headers)
- `send_new(to, subject, body, cc=None, bcc=None)` — compose new email
- `create_draft(to, subject, body, thread_id=None)` — save as Gmail draft
- `send_draft(draft_id)` — send an existing draft
- Uses Gmail API's `messages.send()` and `drafts.create()`
- All messages use base64url encoding, proper MIME structure
- After send: store in local DB as Email with `is_sent=True`

---

### Step 2: DB Schema Updates + Migration
**Edit:** `src/db/models.py`, new Alembic migration

New columns on Thread:
- `goal` (Text, nullable) — freeform goal
- `acceptance_criteria` (Text, nullable)
- `goal_status` (String, default=None) — pending/in_progress/achieved/failed

New models:
- **Draft** — id, thread_id (FK), to_addresses (JSON), cc (JSON), subject, body, status (pending/approved/rejected/sent), created_at, updated_at
- **AuditLog** — id, timestamp, action_type, thread_id (FK nullable), email_id (FK nullable), details (JSON)
- **Playbook** — id, name, description, content (Text), created_at

Run `alembic revision --autogenerate` + `alembic upgrade head`

---

### Step 3: Thread State Machine
**New file:** `src/engine/state_machine.py`

States: NEW, ACTIVE, WAITING_REPLY, FOLLOW_UP, GOAL_MET, ARCHIVED

Transition logic:
- `transition(thread_id, new_state, reason)` — validate + update + audit log
- Auto-transitions triggered by events:
  - Email sent by us → WAITING_REPLY
  - Email received on thread → ACTIVE
  - Follow-up timer expired → FOLLOW_UP
  - Goal status = achieved → GOAL_MET
  - User archives → ARCHIVED
- All transitions are freeform (any → any) per master plan
- Each transition logs to AuditLog

---

### Step 4: Goal + Follow-up Engine
**New files:** `src/engine/goals.py`, `src/engine/followup.py`

Goals (`goals.py`):
- `set_goal(thread_id, goal, criteria)` — set goal + criteria, status=pending
- `update_goal_status(thread_id, status)` — pending/in_progress/achieved/failed
- `check_goal_met(thread_id)` — LLM evaluates latest emails against acceptance criteria
- On achieved: trigger state → GOAL_MET, update context files

Follow-up (`followup.py`):
- `check_follow_ups()` — called by scheduler every 30 min
- Finds threads in WAITING_REPLY where `next_follow_up_date < now`
- Transitions to FOLLOW_UP state
- `set_follow_up(thread_id, days)` — sets next_follow_up_date
- `trigger_follow_up(thread_id)` — immediate follow-up (manual)

Update scheduler (`src/gmail/scheduler.py`) to run `check_follow_ups()` alongside sync.

---

### Step 5: Playbook System
**New file:** `src/engine/playbooks.py`
**New files in:** `playbooks/` directory

4 starter playbooks (markdown templates):
- `schedule-meeting.md`
- `negotiate-price.md`
- `follow-up-generic.md`
- `close-deal.md`

Engine logic:
- `list_playbooks()` — scan playbooks/ dir
- `get_playbook(name)` — read markdown content
- `apply_playbook(thread_id, playbook_name)` — set thread.playbook reference
- Playbooks stored as flat markdown files (no DB model needed for MVP — simplify)

---

### Step 6: API Routes
**New files:** `src/api/routes/drafts.py`, `src/api/routes/goals.py`, `src/api/routes/playbooks.py`
**Edit:** `src/api/routes/threads.py`, `src/api/schemas.py`, `src/main.py`

Thread actions (add to threads router):
- `POST /api/threads/{id}/reply` — body: {body, cc?, bcc?}
- `POST /api/threads/{id}/draft` — body: {body, cc?, bcc?}
- `PUT /api/threads/{id}/state` — body: {state, reason?}
- `PUT /api/threads/{id}/auto-reply` — body: {mode: auto|manual|off}
- `PUT /api/threads/{id}/follow-up` — body: {days}
- `PUT /api/threads/{id}/notes` — body: {notes}

Goals:
- `PUT /api/threads/{id}/goal` — body: {goal, acceptance_criteria?}
- `DELETE /api/threads/{id}/goal` — clear goal
- `PUT /api/threads/{id}/goal/status` — body: {status}

Drafts:
- `GET /api/drafts` — list pending drafts
- `POST /api/drafts/{id}/approve` — send the draft
- `POST /api/drafts/{id}/reject` — reject/delete

Compose:
- `POST /api/compose` — body: {to, subject, body, cc?, bcc?}

Playbooks:
- `GET /api/playbooks` — list available
- `GET /api/playbooks/{name}` — get content
- `POST /api/threads/{id}/playbook` — body: {name}

Update schemas: add goal, acceptance_criteria, goal_status to ThreadDetailOut

---

### Step 7: CLI Commands
**New files:** `src/cli/actions.py`, `src/cli/goals.py`
**Edit:** `src/cli/main.py`

Actions (`actions.py`):
- `ghostpost reply <thread_id> --body "..."` — send reply
- `ghostpost draft <thread_id> --body "..."` — create draft
- `ghostpost compose --to x --subject y --body z` — new email
- `ghostpost drafts` — list pending drafts
- `ghostpost draft-approve <id>` — approve draft
- `ghostpost draft-reject <id>` — reject draft
- `ghostpost toggle <thread_id> --auto-reply on|off|manual`
- `ghostpost followup <thread_id> [--days N]` — set/trigger follow-up

Goals (`goals.py`):
- `ghostpost goal <thread_id> --set "..."` — set goal
- `ghostpost goal <thread_id> --criteria "..."` — set criteria
- `ghostpost goal <thread_id> --status achieved|failed|...`
- `ghostpost playbook list` — list playbooks
- `ghostpost playbook apply <thread_id> <name>`

---

### Step 8: Frontend Updates
**Edit:** `frontend/src/pages/ThreadDetail.tsx`, `frontend/src/api/client.ts`
**New components:** `ReplyComposer.tsx`, `GoalEditor.tsx`, `DraftReview.tsx`

ThreadDetail right sidebar becomes interactive:
- State dropdown (change state)
- Auto-reply toggle (on/off/manual)
- Follow-up days input (editable)
- Goal editor (set goal + criteria, show status)
- Notes textarea (editable, auto-save)
- Playbook selector dropdown

Thread content area additions:
- Reply composer at bottom (textarea + Send/Draft buttons)
- Draft cards with Approve/Reject buttons
- Inline goal status badges

Update API client with all new endpoints.

---

### Step 9: Context Files + Audit Integration
**Edit:** `src/engine/context_writer.py`, `src/engine/enrichment.py`

- Update ACTIVE_GOALS.md with real goal data
- Add DRAFTS.md context file (pending drafts for agent)
- Update EMAIL_CONTEXT.md to include thread states
- AuditLog entries written on every action (reply, draft, state change, goal update)
- WebSocket events for: draft_created, draft_approved, state_changed, goal_updated, reply_sent

---

## Execution Order & Dependencies

```
Step 1 (Gmail send) ─────────────────────────┐
Step 2 (DB schema) ──────────────────────────┤
Step 3 (State machine) ← depends on Step 2   ├─► Step 6 (API) ← depends on 1-5
Step 4 (Goals + Follow-up) ← depends on 2,3  │   Step 7 (CLI) ← depends on 6
Step 5 (Playbooks) ───────────────────────────┘   Step 8 (Frontend) ← depends on 6
                                                   Step 9 (Context) ← depends on 3,4
```

Steps 1, 2, 5 can be done in parallel. Steps 3, 4 depend on 2. Steps 6-9 depend on 1-5.
