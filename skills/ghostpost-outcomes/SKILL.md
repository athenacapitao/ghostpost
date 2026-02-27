---
name: ghostpost_outcomes
description: View completed thread outcomes — extracted knowledge, agreements, decisions, and lessons learned from resolved conversations.
user-invocable: true
metadata: {"openclaw": {"emoji": "📊", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Outcomes

View knowledge extracted from completed conversations. Outcomes capture agreements, decisions, deliveries, and lessons learned.

## When to invoke

- Reviewing what was achieved in past conversations
- Looking up past agreements or decisions before a new interaction
- Learning from historical outcomes to improve future replies
- Manually extracting knowledge from a completed thread

## Entry point

```bash
ghostpost outcomes list --json
```

## Commands

```bash
ghostpost outcomes list --json                            # List recent outcomes (default: 20)
ghostpost outcomes list --limit 50 --json                 # More outcomes
ghostpost outcomes get <thread_id> --json                # Get specific thread's outcome
ghostpost outcomes extract <thread_id> --json            # Manually trigger extraction
cat context/COMPLETED_OUTCOMES.md                         # Context file with last 30 days
```

## Outcome types

- **agreement** — Terms agreed upon (pricing, scope, timeline)
- **decision** — Choice made (vendor, approach, direction)
- **delivery** — Document or deliverable received/sent
- **meeting** — Meeting scheduled or completed
- **other** — Miscellaneous resolved items

## Rules

- Auto-extracted when thread reaches GOAL_MET or ARCHIVED — no manual trigger needed
- Stored in: DB + `memory/outcomes/YYYY-MM-topic.md` + `context/COMPLETED_OUTCOMES.md`
- Context file shows last 30 days only — use CLI for older outcomes
- Use past outcomes to inform approach in new conversations
