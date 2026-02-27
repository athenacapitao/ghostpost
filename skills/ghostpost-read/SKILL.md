---
name: ghostpost_read
description: Read specific email threads, AI briefs, contact profiles, and attachments from GhostPost.
user-invocable: true
metadata: {"openclaw": {"emoji": "📧", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Read

Read specific email threads, AI-generated briefs, contact profiles, and attachments. Use after triage or context identifies something needing attention.

## When to invoke

- Triage or context identifies a thread needing attention
- User asks about a specific email conversation
- Need to read a thread before replying or taking action
- Looking up contact details or downloading attachments

## Entry point

```bash
ghostpost brief <id> --json
```

## Commands

### Thread briefs (recommended — includes analysis, goals, security, actions)

```bash
ghostpost brief <id> --json                              # Structured brief — BEST starting point
```

### Thread listing

```bash
ghostpost threads --json                                  # List threads (default 20)
ghostpost threads --state ACTIVE --json                  # Filter by state
ghostpost threads --state ACTIVE --limit 20 --json       # With pagination
```

### Full thread data

```bash
ghostpost thread <id> --json                             # Full thread with all emails
ghostpost email <id> --json                              # Single email with headers, body, attachments
```

### Contacts

```bash
ghostpost contacts --json                                # List all contacts
ghostpost contacts --search "name" --limit 20 --json    # Search contacts by name or email
ghostpost contact <id> --json                            # Contact detail with enrichment profile
```

### Attachments

```bash
ghostpost attachment <id> --output /path/to/file --json  # Download attachment
```

## Rules

- Prefer `ghostpost brief` over `ghostpost thread` — briefs include analysis, goals, security score, and Available Actions
- Thread context files (`context/threads/{id}.md`) have Available Actions with exact CLI commands
- Valid state filters: NEW, ACTIVE, WAITING_REPLY, FOLLOW_UP, GOAL_MET, ARCHIVED
- For broad inbox overview, use ghostpost-context instead of listing all threads
