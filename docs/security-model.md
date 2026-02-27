# GhostPost Security Model

All inbound email is treated as untrusted data. Every email passes through 6 independent security layers before its content reaches an LLM or triggers any action.

## The 6 Layers

| Layer | Module | When It Runs | What It Does |
|-------|--------|--------------|--------------|
| 1 | `security/sanitizer.py` `sanitize_html()` | On every sync | Strips HTML comments, `<script>`, `<style>`, event handlers; decodes HTML entities |
| 2 | `security/sanitizer.py` `isolate_content()` | Before LLM calls | Wraps email content in `=== UNTRUSTED EMAIL CONTENT START/END ===` markers |
| 3 | `security/injection_detector.py` | On every sync | Scans subject + body for 18 injection patterns; quarantines critical/high matches |
| 4 | `security/commitment_detector.py` | At pre-send check | Detects commitments (financial, time, resource) in outgoing body; raises warnings |
| 5 | `engine/security.py` | After sync, on enrich | Rule-based 0-100 score per email; thread average tracked |
| 6 | `security/safeguards.py` `check_send_allowed()` | Before every send | Master gate: blocklist + rate limit (hard blocks) + commitments + sensitive topics + score (warnings) |

Layers 1-3 run automatically during Gmail sync. Layers 4-6 run at send time via `check_send_allowed()`.

## Security Scoring (Layer 5)

Each email receives a 0-100 integer score. Thread `security_score_avg` is the mean of its emails.

### Scoring Factors

| Factor | Condition | Points |
|--------|-----------|--------|
| Known sender | Contact record exists | +30 |
| Known sender | No contact record | +0 |
| Prior threads | Sender has >1 thread | +20 |
| Prior threads | First contact | +0 |
| Clean patterns | No suspicious text | +20 |
| Suspicious patterns | Injection-like language detected | -30 |
| Safe links | No links, or all links on safe domain list | +15 |
| Unknown links | Any link to unlisted domain | -15 |
| No attachments | Email has no attachments | +15 |
| Safe attachments | Has attachments, none risky | +10 |
| Risky attachments | `.exe`, `.bat`, `.ps1`, `.vbs`, etc. | -20 |

Score is clamped to [0, 100]. A brand-new unknown sender with a clean email scores 50 (0+0+20+15+15). A known repeat contact scores 85 (30+20+20+15+0).

### Safe Domain List

Links to these domains do not trigger the unknown-links penalty: `google.com`, `gmail.com`, `github.com`, `linkedin.com`, `notion.so`, `slack.com`, `zoom.us`, `microsoft.com`, `apple.com`, `dropbox.com`, `youtube.com`, plus common social/productivity domains.

## Injection Detection (Layer 3)

18 regex patterns across 3 severity levels scan subject and all body fields.

### Severity Levels and Auto-Quarantine

| Severity | Examples | Auto-Quarantine |
|----------|----------|-----------------|
| `critical` | System prompt override, role hijack, `<system>` tags | Yes |
| `high` | "Send email to...", "transfer $N", data exfiltration commands | Yes |
| `medium` | Delimiter escapes, base64 markers, hidden unicode, jailbreak phrases | No (logged only) |

Critical and high matches create a `SecurityEvent` with `quarantined=True` and `resolution="pending"`. Medium matches create a `SecurityEvent` but do not quarantine.

## Pre-Send Check (Layer 6)

`check_send_allowed()` runs before every outbound email. It returns `{allowed, reasons, warnings}`.

### Hard Blocks (send is rejected, HTTP 403)

| Condition | Trigger |
|-----------|---------|
| Recipient on blocklist | Any recipient email matches blocklist entry |
| Hourly rate limit | `>= 20 sends/hr` per actor (tracked in Redis, resets hourly) |

### Soft Warnings (send proceeds, warnings returned in response)

| Condition | Trigger |
|-----------|---------|
| Commitment detected | Outgoing body contains financial/time/resource commitments |
| Sensitive topics | Body contains: `legal`, `lawsuit`, `tax`, `irs`, `medical`, `hipaa`, `confidential`, `nda`, `termination`, `harassment`, `discrimination`, etc. |
| Low thread score | `thread.security_score_avg < 50` |

## Resolving Quarantine Events

Quarantined emails have `resolution="pending"`. They do not block the thread — they flag it for review.

```bash
# List pending quarantine events
ghostpost quarantine list --json

# Approve (mark as safe)
ghostpost quarantine approve <event_id> --json

# Dismiss (acknowledge, not safe but no action needed)
# Use the API: POST /api/security/quarantine/{event_id}/dismiss
```

After approving, the thread can proceed normally. The approval is logged to the audit trail.

## Rate Limiting Details

- **Limit:** 20 sends per hour per actor (`user` or `system`)
- **Window:** Rolling 1-hour bucket keyed by `ghostpost:rate:{actor}:{YYYYMMDDHH}` in Redis
- **Reset:** Automatically expires after 3600s (Redis TTL)
- **Scope:** Separate counters for `user`-initiated sends and `system`-initiated sends
- **On breach:** `rate_limit_exceeded` security event logged at `high` severity; send is hard-blocked

## Audit Trail

Every action writes to `AuditLog` and publishes a WebSocket event. Security events write to `SecurityEvent` separately.

```bash
ghostpost audit --hours 24 --json   # Recent actions
ghostpost quarantine list --json     # Pending security events
```
