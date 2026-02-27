# GhostPost Thread State Machine

Every thread has a `state` field that tracks its lifecycle. State changes are logged to the audit trail and broadcast over WebSocket.

## States

| State | Meaning | Typical Next States |
|-------|---------|---------------------|
| `NEW` | Thread just arrived, not yet acted on | `ACTIVE`, `ARCHIVED` |
| `ACTIVE` | Thread requires attention or is being worked | `WAITING_REPLY`, `GOAL_MET`, `ARCHIVED` |
| `WAITING_REPLY` | A reply was sent; waiting for a response | `ACTIVE` (reply received), `FOLLOW_UP` (timer expired) |
| `FOLLOW_UP` | Follow-up window elapsed without a response | `ACTIVE`, `WAITING_REPLY`, `ARCHIVED` |
| `GOAL_MET` | Thread goal has been achieved | `ARCHIVED` |
| `ARCHIVED` | Thread closed, no further action expected | — |

## Auto-Transitions

These happen automatically without any manual trigger.

### On Send (`auto_transition_on_send`)

Triggered immediately after a reply or composed email is sent.

- Thread moves to `WAITING_REPLY`
- `thread.next_follow_up_date` is set to `now + thread.follow_up_days` (default 3 days)

### On Receive (`auto_transition_on_receive`)

Triggered when Gmail sync detects a new inbound email on the thread.

- Only fires if current state is `WAITING_REPLY` or `FOLLOW_UP`
- Thread moves to `ACTIVE`
- `thread.next_follow_up_date` is cleared

### On Follow-Up Timer (`check_follow_ups`)

Run by the scheduler (checked at every sync cycle, ~30 min).

- Finds all threads in `WAITING_REPLY` where `next_follow_up_date <= now`
- Transitions each to `FOLLOW_UP`
- Publishes `follow_up_triggered` WebSocket event
- Writes a stale-thread notification to `context/ALERTS.md`

## Manual Transitions

Any state can be set manually via the API or CLI:

```bash
# Via CLI
ghostpost state <thread_id> ARCHIVED --json
ghostpost state <thread_id> GOAL_MET --json

# Via API
PUT /api/threads/{thread_id}/state
Body: {"state": "ARCHIVED", "reason": "resolved offline"}
```

Valid states for manual transition: `NEW`, `ACTIVE`, `WAITING_REPLY`, `FOLLOW_UP`, `GOAL_MET`, `ARCHIVED`

Transitioning to the same state the thread is already in is a no-op (returns without error).

## Knowledge Extraction

Knowledge extraction runs automatically when a thread transitions to `GOAL_MET` or `ARCHIVED`. It is a background task (`asyncio.create_task`) and does not block the state transition.

- Calls `src/engine/knowledge.py` `on_thread_complete(thread_id)`
- Extracts outcome data using LLM and stores it as a `ThreadOutcome` record
- Requires LLM to be available (`MINIMAX_API_KEY` set)
- Can also be triggered manually: `POST /api/threads/{thread_id}/extract`

If the thread is not in `GOAL_MET` or `ARCHIVED`, the manual extract endpoint returns 400.

## Follow-Up Scheduling Details

| Property | Default | Override |
|----------|---------|----------|
| `follow_up_days` | 3 days | `PUT /api/threads/{id}/follow-up` or `ghostpost follow-up <id> <days>` |
| `next_follow_up_date` | Set on send | Auto-cleared on receive; recalculated on re-send |
| Scheduler frequency | ~30 minutes | Tied to Gmail sync heartbeat |

The follow-up date is stored as a UTC timestamp in `thread.next_follow_up_date`. It is only evaluated while the thread is in `WAITING_REPLY` state.

## State Flow Diagram

```
NEW ──────────────────────────────────────────► ARCHIVED
 │                                                  ▲
 ▼                                                  │
ACTIVE ──── (send reply) ──► WAITING_REPLY ─── (timer) ──► FOLLOW_UP
 ▲                                 │                              │
 │                                 │ (receive email)              │
 └─────────────────────────────────┘◄─────────────────────────────┘
 │
 ▼
GOAL_MET ────────────────────────────────────► ARCHIVED
  (knowledge extraction fires on both GOAL_MET and ARCHIVED)
```
