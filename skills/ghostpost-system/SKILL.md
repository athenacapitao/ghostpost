---
name: ghostpost_system
description: System operations — health checks, email sync, AI enrichment, storage stats, batch job management, and contact web enrichment.
user-invocable: true
metadata: {"openclaw": {"emoji": "🖥️", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost System

System operations for health monitoring, manual sync, AI enrichment, and batch job management.

## When to invoke

- Checking if GhostPost is running and healthy
- Manually triggering a sync outside the automatic schedule
- Running AI enrichment manually
- Checking system stats (thread counts, DB size)
- Managing batch jobs

## Entry point

```bash
ghostpost health --json
```

## Commands

### Health and status

```bash
ghostpost health --json                                   # Check API, DB, and Redis health
ghostpost status --json                                   # System overview: health + inbox snapshot
ghostpost stats --json                                    # Storage stats: thread count, emails, contacts, DB size
```

### Email sync

```bash
ghostpost sync --json                                     # Trigger email sync from Gmail (normally auto every 10 min)
```

### AI enrichment

```bash
ghostpost enrich --json                                   # Full AI enrichment (categorize, summarize, analyze)
ghostpost enrich-web <contact_id> --json                 # Enrich specific contact via web/domain research
```

### Batch jobs

```bash
ghostpost batch list --json                               # List all batch jobs
ghostpost batch detail <batch_id> --json                 # Batch job details and progress
ghostpost batch cancel <batch_id> --json                 # Cancel a running batch job
```

## Automatic processes (no agent action needed)

- Gmail sync: every 10 minutes
- After sync: security scoring → context files → LLM enrichment → follow-up checks
- Follow-up scheduler: checks overdue timers on each sync

## Rules

- Sync runs automatically every 10 minutes — only trigger manually if urgent
- After sync: enrichment runs automatically (security scoring → context files → LLM analysis)
- Enrichment requires LLM API key for AI features; security scoring + context files work without it
- Do NOT trigger sync more than once per 10 minutes — unnecessary Gmail API calls
- `ghostpost health` checks: API server, PostgreSQL, Redis
- For thread management, use ghostpost-manage; for security, use ghostpost-security
