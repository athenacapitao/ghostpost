---
name: ghost_research
description: 8-phase deep company research pipeline producing tailored outreach emails backed by peer intelligence. Handles single campaigns, batch processing, and identity management.
user-invocable: true
metadata: {"openclaw": {"emoji": "🔬", "requires": {"bins": ["ghostpost"], "env": ["MINIMAX_API_KEY", "SEARCH_API_KEY"]}}}
---

# Ghost Research

Run multi-phase research campaigns for B2B company outreach. The pipeline produces 8 markdown documents per company (7 when no contact name is provided), culminating in a tailored email draft backed by real peer intelligence and verified contact discovery.

## When to invoke

- User provides a company name and goal for outreach
- Preparing personalized emails with peer-backed evidence
- Running batch research across multiple target companies
- Managing the research queue (pause, resume, skip, retry)

## Entry point

```bash
ghostpost research run "Company" --goal "..." --identity <name> --json
```

**Verbose output is always on.** The pipeline streams real-time progress to the CLI, including web search counts, LLM calls, file writes, and phase transitions. AI agents see every step as it happens — no `--verbose` flag needed.

## Verbose output format

When running a campaign, expect timestamped entries streamed in real time:

```
  [14:23:01] [--] Pipeline started for campaign #42
  [14:23:01] [P1] Starting Phase 1: Input Collection...
  [14:23:01] [P1] Validating inputs for Acme Corp
  [14:23:01] [P1] Identity 'default': valid
  [14:23:02] [P1] Wrote input file: research/acme_corp/00_input.md
  [14:23:02] [P1] Phase 1: Input Collection complete
  [14:23:02] [P2] Starting Phase 2: Deep Research...
  [14:23:02] [P2] Executing 14 web searches across 4 rounds
  [14:23:15] [P2] Web research complete: 87 results, 12 pages fetched
  [14:23:15] [P2] Calling LLM to generate company dossier...
  [14:23:38] [P2] LLM dossier generated (3421 chars)
  ...
```

The verbose log is also available in JSON via `research_data.verbose_log`:

```json
{"ts": "14:23:02", "phase": 2, "msg": "Executing 14 web searches across 4 rounds"}
```

## Commands

### Single campaign

```bash
ghostpost research run "Company" --goal "..." --identity <name> --json                                    # Start + watch (default)
ghostpost research run "Company" --goal "..." --no-watch --json                                           # Start without watching
ghostpost research run "Company" --goal "..." --identity <name> --language pt-PT --country Portugal --industry "Tech" --json   # Full options
ghostpost research run "Company" --goal "..." --contact-name "John" --contact-email "j@c.com" --contact-role "CTO" --json     # With known contact
```

### Monitor campaigns

```bash
ghostpost research status <campaign_id> --json            # Campaign progress + full verbose log history
ghostpost research status <campaign_id> --watch --json    # Live watch with verbose streaming
ghostpost research list --json                            # List all campaigns
ghostpost research list --status completed --json         # Filter by status
ghostpost research output <id> 06_email_draft.md --json  # Read final email draft
ghostpost research output <id> 04_peer_intelligence.md --json  # Read peer intelligence (CRITICAL phase)
```

### Identities

```bash
ghostpost research identities --json                      # List available sender identities
```

### Batch processing

```bash
ghostpost research batch <file.json> --name "Q1 Outreach" --json    # Start batch
ghostpost research queue <batch_id> --json                            # View batch queue
ghostpost research pause <batch_id> --json                           # Pause running batch
ghostpost research resume <batch_id> --json                          # Resume paused batch
ghostpost research skip <campaign_id> --json                         # Skip queued campaign
ghostpost research retry <campaign_id> --json                        # Retry failed campaign
```

## Pipeline phases

| Phase | Output File | Description |
|-------|-------------|-------------|
| 1 | `00_input.md` | Input & Context |
| 2 | `01_company_dossier.md` | Deep Research |
| 3 | `02_opportunity_analysis.md` | Opportunity Analysis |
| 4 | `03_contacts_search.md` | Contacts Search (find best contact email) |
| 5 | `04b_person_profile.md` | Person Research — conditional, only when contact_name provided |
| 6 | `04_peer_intelligence.md` | Peer Intelligence (critical — never skip) |
| 7 | `05_value_proposition_plan.md` | Value Proposition |
| 8 | `06_email_draft.md` | Email Composition |

## Post-research workflow

After research completes, send the email:

```bash
ghostpost research output <id> 06_email_draft.md --json  # Review draft
ghostpost compose --to <email> --subject "..." --body "..." --goal "..." --json  # Send via compose
ghostpost followup <thread_id> --days 5 --json            # Set follow-up timer
```

## Rules

- Process ONE company at a time — NEVER run campaigns in parallel
- Phase 6 (Peer Intelligence) is NON-NEGOTIABLE — never skip it
- Outreach emails MUST be under 150 words
- Default email language: Portuguese (Portugal); research docs always English
- NEVER send research email without approval unless auto_reply_mode is "autonomous"
- All output persists permanently in `research/[company_slug]/` (7-8 markdown files depending on whether contact_name was provided)
- Identity files in `config/identities/` — each defines company, sender, email
- Requires MINIMAX_API_KEY and SEARCH_API_KEY environment variables
- **Always use `--watch` (default)** — verbose output is essential for monitoring pipeline health
- Verbose log entries are stored in `research_data.verbose_log` and persist in the DB for post-mortem analysis
