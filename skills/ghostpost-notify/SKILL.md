---
name: ghostpost_notify
description: Configure notification preferences — toggle alerts for new emails, goals, security events, drafts, and stale threads via Telegram.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔔", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Notify

Configure which events trigger Telegram notifications. Control noise level by enabling or disabling specific alert types.

## When to invoke

- Adjusting notification noise level
- Enabling/disabling specific alert types
- Checking current notification preferences
- User asks to stop or start receiving certain alerts

## Entry point

```bash
ghostpost alerts --json
```

## Commands

### View alerts

```bash
ghostpost alerts --json                                           # View all active alerts
ghostpost settings list --json                                    # See all settings including notification toggles
ghostpost settings get notification_new_email --json              # Check specific toggle
```

### Toggle notifications

```bash
ghostpost settings set notification_new_email false               # Disable new email alerts
ghostpost settings set notification_goal_met true                 # Enable goal completion alerts
ghostpost settings set notification_security_alert true           # Enable security alerts
ghostpost settings set notification_draft_ready true              # Enable draft-ready alerts
ghostpost settings set notification_stale_thread true             # Enable stale thread alerts
```

## Available notification settings

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `notification_new_email` | true | New email received |
| `notification_goal_met` | true | Goal achieved on a thread |
| `notification_security_alert` | true | Security event detected |
| `notification_draft_ready` | true | Draft awaiting approval |
| `notification_stale_thread` | true | Thread overdue for follow-up |

## Rules

- All default to true — disable to reduce noise
- All notifications go to Athena's Telegram account
- Disabling `notification_security_alert` means incidents ONLY appear in audit log
- `notification_stale_thread` respects per-thread follow-up timer
- Settings persist in database and survive restarts
