---
name: ghostpost_manage
description: Manage thread lifecycle — change state, toggle auto-reply mode, set follow-up timers, add notes, and configure system settings.
user-invocable: true
metadata: {"openclaw": {"emoji": "⚙️", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Manage

Manage thread lifecycle and system settings. Change states, toggle auto-reply, set follow-up timers, add notes.

## When to invoke

- Archiving a completed thread
- Setting follow-up timers after sending a reply
- Changing auto-reply mode for a thread
- Adding notes to a thread for future reference
- Configuring system-wide settings

## Entry point

```bash
ghostpost state <id> <STATE> --json
```

## Commands

### Thread state

```bash
ghostpost state <id> ACTIVE --json                       # States: NEW, ACTIVE, WAITING_REPLY, FOLLOW_UP, GOAL_MET, ARCHIVED
ghostpost state <id> ARCHIVED --reason "resolved" --json # Archive with reason (logged in audit)
```

### Auto-reply mode

```bash
ghostpost toggle <id> --mode draft --json                # off (default), draft, auto
```

### Follow-up timers

```bash
ghostpost followup <id> --days 5 --json                  # Triggers FOLLOW_UP when overdue
```

### Thread notes

```bash
ghostpost notes <id> --json                               # View thread notes
ghostpost notes <id> --text "Important: prefers phone" --json  # Set notes (visible in briefs)
```

### System settings

```bash
ghostpost settings list --json                            # View all settings
ghostpost settings get <key> --json                       # Get specific setting
ghostpost settings set <key> <value>                      # Update setting
ghostpost settings delete <key> --json                    # Reset to default
ghostpost settings bulk key1=val1 key2=val2 --json       # Update multiple
```

## State machine

```
NEW → ACTIVE → WAITING_REPLY → FOLLOW_UP → GOAL_MET → ARCHIVED
```

- Auto-transitions: reply sent → WAITING_REPLY; new email → ACTIVE; timer expires → FOLLOW_UP
- Manual transitions: any state → any state via `ghostpost state`

## Auto-reply modes

- **off** — No auto replies. Agent only replies when explicitly asked. (Default, safest)
- **draft** — Agent creates drafts for review before sending. (Recommended for important threads)
- **auto** — Agent sends directly, safeguard checks still apply. (Only for low-risk threads)

## Rules

- For goal management, use ghostpost-goals; for system ops, use ghostpost-system
- Settings persist in database and survive restarts
- Archive reasons are logged in the audit trail
