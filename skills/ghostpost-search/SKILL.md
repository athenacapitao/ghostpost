---
name: ghostpost_search
description: Search GhostPost emails by keyword, sender, subject, or body content across all threads and contacts.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔍", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Search

Search emails by keyword, sender, subject, or body content. Use when looking for specific conversations or contacts.

## When to invoke

- Looking for emails about a specific topic
- Finding conversations with a specific person
- Need to locate a thread ID before taking action

## Entry point

```bash
ghostpost search "keyword" --json
```

## Commands

```bash
ghostpost search "keyword" --json                        # Search subject + body
ghostpost search "john@example.com" --json              # Search by sender email
ghostpost search "meeting" --limit 20 --json            # Control result count (default: 10)
ghostpost contacts --search "name" --json               # Search contacts by name or email
```

## Rules

- Searches subject and body content — not headers or attachments
- Results return thread IDs — drill into with `ghostpost brief <id> --json`
- For listing threads by state, use `ghostpost threads --state <STATE>` instead
- For broad inbox awareness, use ghostpost-context instead
