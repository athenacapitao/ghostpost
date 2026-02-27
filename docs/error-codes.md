# GhostPost Error Codes

## CLI Error Envelope (--json mode)

All CLI commands accept a `--json` flag. When used, the output is wrapped in a consistent envelope:

- Success: `{"ok": true, "data": {...}}`
- Error: `{"ok": false, "error": "...", "code": "...", "retryable": true|false, "status": 0}`

The `status` field is the HTTP status code (0 for connection errors). The `retryable` field indicates whether the operation is safe to retry without changes.

## Error Codes

| Code | Status | Retryable | Meaning | Recovery |
|------|--------|-----------|---------|----------|
| `CONNECTION_ERROR` | 0 | Yes | API server unreachable | Check `pm2 status ghostpost-api`, retry in 5s |
| `HTTP_4XX` | 4xx | No | Client error (bad request, auth, not found) | Inspect `error` field for detail |
| `HTTP_5XX` | 5xx | Yes | Server error | Check `pm2 logs ghostpost-api --lines 50` |

Note: The CLI uses two generic codes (`HTTP_4XX`, `HTTP_5XX`) rather than per-status codes. The specific HTTP status integer is always present in the `status` field.

### Key HTTP Statuses Within HTTP_4XX

| Status | Meaning | Common Cause |
|--------|---------|--------------|
| 401 | Unauthenticated | Token expired or missing |
| 403 | Forbidden / Blocked | Blocklist hit, rate limit, or safeguard block |
| 404 | Not found | Invalid thread/draft/email ID |
| 409 | Conflict | Outcome already extracted for thread |
| 422 | Validation error | Missing or invalid request field |
| 429 | Rate limited | Hourly send limit reached (20/hr default) |

### Key HTTP Statuses Within HTTP_5XX

| Status | Meaning | Common Cause |
|--------|---------|--------------|
| 500 | Server error | Bug or unexpected state |
| 503 | Service unavailable | LLM unreachable or enrichment failed |

## Common Recovery Patterns

### Server unreachable (CONNECTION_ERROR)

```bash
pm2 status ghostpost-api
pm2 restart ghostpost-api
# Wait ~5s for startup, then retry
ghostpost health --json
```

### Rate limited (status 429)

The hourly limit is 20 sends per actor. Check recent activity and wait until the next hour boundary.

```bash
ghostpost audit --hours 1 --json
# Wait until the top of the hour, then retry
```

### Safeguard block (status 403, blocked: true)

The response body includes `{"blocked": true, "reasons": [...]}`. Common causes:

- Recipient is on the blocklist: `ghostpost blocklist list --json`
- Hourly send limit exceeded: see rate limiting above
- Thread security score below 50: review `ghostpost thread <id> --json` security_score_avg

```bash
# Remove from blocklist
ghostpost blocklist remove <email> --json

# Check quarantine events
ghostpost quarantine list --json
```

### Validation error (status 422)

Check the `error` field for which field failed. Required fields by operation:

| Operation | Required Fields |
|-----------|----------------|
| Reply | `body` |
| Compose | `to`, `subject`, `body` |
| Draft create | `to`, `subject`, `body` |
| Goal set | `goal`, `acceptance_criteria` |
| State change | `state` (must be a valid state name) |

### Thread not found (status 404)

Verify the thread ID exists:

```bash
ghostpost threads --json | python3 -c "import sys,json; [print(t['id']) for t in json.load(sys.stdin)['data']['items']]"
```

### LLM unavailable (status 503)

Some operations require the LLM (enrichment, reply generation, goal check, knowledge extraction). Verify the `MINIMAX_API_KEY` is set and the LLM endpoint is reachable:

```bash
ghostpost enrich status --json
```
