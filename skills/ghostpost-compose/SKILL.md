---
name: ghostpost_compose
description: Compose and send new emails to start new conversations with optional goals, playbooks, follow-up timers, and priority settings.
user-invocable: true
metadata: {"openclaw": {"emoji": "✉️", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Compose

Start new email conversations. Supports goals, playbooks, follow-up timers, auto-reply modes, and priority settings.

## When to invoke

- Reaching out to someone for the first time
- Starting a new email thread (not replying to existing)
- Sending research-generated outreach emails
- User asks to email someone new

## Entry point

```bash
ghostpost compose --to email@example.com --subject "..." --body "..." --json
```

## Commands

```bash
# Minimum required
ghostpost compose --to email@example.com --subject "..." --body "..." --json

# With CC
ghostpost compose --to a@b.com --cc c@d.com --subject "..." --body "..." --json

# With goal tracking
ghostpost compose --to a@b.com --subject "..." --body "..." --goal "Get meeting" --acceptance-criteria "Date confirmed" --json

# With follow-up timer
ghostpost compose --to a@b.com --subject "..." --body "..." --follow-up-days 5 --json

# With playbook
ghostpost compose --to a@b.com --subject "..." --body "..." --playbook schedule-meeting --json

# Full options
ghostpost compose --to a@b.com --subject "..." --body "..." --auto-reply draft --priority high --json
```

## Rules

- Required flags: `--to`, `--subject`, `--body` (everything else optional)
- Check `context/RULES.md` for reply style, blocklist, and sending rules
- Safeguard checks run before sending: blocklist, rate limit, sensitive topics
- Thread auto-created with state WAITING_REPLY
- Batch sends (> 20 recipients) auto-queue for background processing
- For replies to existing threads, use ghostpost-reply instead
