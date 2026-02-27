---
name: ghostpost_playbook
description: Apply reusable workflow templates to email threads for meetings, negotiations, follow-ups, and deals. Create custom playbooks for recurring patterns.
user-invocable: true
metadata: {"openclaw": {"emoji": "📝", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Playbook

Apply reusable workflow templates to email threads. Playbooks provide structured guidance for common patterns like scheduling meetings, negotiating, and closing deals.

## When to invoke

- Thread needs a structured approach (negotiation, scheduling, follow-up)
- Applying a standard workflow to a conversation
- Creating a reusable template for recurring email patterns

## Entry point

```bash
ghostpost playbooks --json
```

## Commands

### Browse and apply

```bash
ghostpost playbooks --json                                   # List all available playbooks
ghostpost playbook <name> --json                             # View playbook content/steps
ghostpost apply-playbook <thread_id> <name> --json           # Apply playbook to thread
```

### Create and manage

```bash
ghostpost playbook-create <name> --body "## Steps\n1. ..."  # Create custom playbook
ghostpost playbook-update <name> --body "..."                # Update playbook content
ghostpost playbook-delete <name>                             # Delete a custom playbook
```

## Built-in playbooks

- **schedule-meeting** — Propose times, confirm, send calendar invite
- **negotiate-price** — Anchor, counter, concede, close
- **follow-up-generic** — Gentle reminder, escalation, final notice
- **close-deal** — Summarize terms, request signature, confirm

## Rules

- Applying sets the thread's `active_playbook` field — visible in `ghostpost brief`
- Playbooks are markdown files in `/home/athena/ghostpost/playbooks/`
- Create custom playbooks for patterns that repeat across threads
- Playbooks provide guidance — still compose replies via ghostpost-reply
