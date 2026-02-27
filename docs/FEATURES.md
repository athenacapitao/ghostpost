# GhostPost — Features Reference

> Extracted from MASTER_PLAN.md Sections 3, 6, 7, 9

---

## Email Mirror & Sync

| Aspect | Decision |
|--------|----------|
| **Source** | Gmail API (REST, push-capable) |
| **Account** | athena@gmail.com |
| **Sync** | 30-minute heartbeat polling |
| **History** | No limit — import everything |
| **Threading** | Gmail native thread grouping |
| **Storage** | PostgreSQL + markdown context files |
| **Monitoring** | Dashboard indicator for storage usage |

**Every email stores:** Message ID, Thread ID, Gmail ID, From, To, CC, BCC, Date (with timezone), Subject, Body (plain + HTML), Headers (all), Attachment metadata, Labels (Gmail native).

---

## Agent-Enriched Metadata

### Per Thread

| Field | Description | Set By |
|-------|-------------|--------|
| `category` | Agent-invented freeform | Agent (first email, batch job) |
| `summary` | Structured summary, updated on each new email | Agent (auto) |
| `state` | Lifecycle state (NEW/ACTIVE/WAITING_REPLY/FOLLOW_UP/GOAL_MET/ARCHIVED) | Agent + User |
| `priority` | low / medium / high / critical | Agent |
| `sentiment` | positive / neutral / negative / frustrated | Agent (per email) |
| `urgency` | low / medium / high / critical | Agent (per email) |
| `action_required` | yes/no + description | Agent (per email) |
| `auto_reply` | auto / manual / off | User (dashboard) |
| `goal` | Freeform goal/objective | User (dashboard/Telegram) |
| `acceptance_criteria` | How to know goal is met | User |
| `goal_status` | pending / in_progress / achieved / failed | Agent |
| `follow_up_days` | Days before auto-follow-up (default: 3) | User |
| `follow_up_suggestion` | Agent's suggestion for future follow-up | Agent |
| `security_score` | 0-100 safety score | Agent |
| `playbook` | Link to playbook template | User |
| `notes` | Freeform context notes for agent | User |
| `blocklist_override` | Force manual mode | System |

### Per Contact

| Field | Description |
|-------|-------------|
| `name` | Full name |
| `email` / `aliases` | Primary + known alternatives |
| `relationship_type` | client / vendor / friend / colleague / unknown |
| `communication_frequency` | daily / weekly / monthly / rare |
| `avg_response_time` | Average time to respond |
| `preferred_style` | brief / detailed / formal / casual |
| `topics` | Topics discussed |
| `last_interaction` | Date of last email |
| `enrichment_source` | email_history / web_search / proxycurl |
| `notes` | Agent observations |

---

## Thread State Machine

States are **interchangeable** — can move between any states:

```
       ┌──────────────────────────────────────────┐
       │                                          │
       ▼                                          │
     [NEW] ──► [ACTIVE] ◄──► [WAITING_REPLY] ◄───┤
                  │                 │              │
                  │                 ▼              │
                  │           [FOLLOW_UP] ─────────┘
                  │                 │
                  ▼                 ▼
            [GOAL_MET] ──► [ARCHIVED]
```

---

## Auto-Reply System

| Mode | Behavior |
|------|----------|
| **Auto** | Agent sends immediately using thread context + goal + playbook |
| **Manual** | Agent creates draft, waits for approval (dashboard/Telegram) |
| **Off** | No agent action |

**Override rules (force manual regardless of toggle):**
- Commitment detection (money, legal, deadlines)
- Security score below threshold
- Sensitive topic detection
- Unknown sender + high urgency
- Prompt injection detected

---

## Follow-Up System

- **Default:** 3 days
- **Per-thread override** in dashboard
- **Tone:** Same as original (no escalation)
- **Trigger:** Timer expires + thread in WAITING_REPLY
- **Stale:** Flag to user via Telegram if still no reply after follow-up

---

## Goal & Objective System

- Freeform goals in natural language
- Measurable acceptance criteria
- Multi-goal support (sequential per thread)
- On goal met: Telegram notification + mark GOAL_MET + suggest follow-up
- Lifecycle: pending → in_progress → achieved / failed
- Playbooks: Reusable markdown templates (negotiate price, schedule meeting, etc.)

---

## Structured Briefs

When the agent acts on a thread, Ghost Post generates:

```markdown
## Thread Brief: Project Pricing Discussion
- **Thread ID:** abc123
- **Participants:** john@acme.com (John Smith, CTO), you
- **State:** WAITING_REPLY (from them, 2 days)
- **Priority:** High | **Sentiment:** Neutral | **Security:** 95/100
- **Goal:** Negotiate price to €5,000 or below
- **Acceptance Criteria:** Written agreement on price in email
- **Summary:** John proposed €7,000. You countered at €4,500. He's thinking.
- **Last message:** John (Feb 22) — "Let me discuss with my team."
- **Contact:** Responds in 1-2 days. Prefers concise emails.
```

---

## UI Dashboard

### Layout: Side-by-Side

```
┌─────────────────────────────┬──────────────────────────┐
│  THREAD (Left 60%)          │  CONTEXT (Right 40%)     │
│  Thread summary (top)       │  State, Auto-reply toggle│
│  Email chain                │  Goal + Criteria         │
│  Draft review area          │  Follow-up settings      │
│  Compose reply              │  Contact info            │
│                             │  Security score          │
│                             │  Notes, Playbook         │
│                             │  Audit log               │
└─────────────────────────────┴──────────────────────────┘
```

### Pages
- **Login** — JWT auth
- **Threads** — Main list + detail (side-by-side)
- **Compose** — New email with optional goal/playbook
- **Settings** — Reply style, follow-up defaults, blocklists, thresholds, sync status
- **Dashboard** — Stats, activity feed, attention queue, storage bar

### Real-Time (WebSocket)
- New email → thread list updates
- Draft created → badge appears
- Goal met → status update
- Security alert → quarantine badge

---

## Telegram Notifications

### Notify:
- Emails requiring attention (high urgency, unknown sender needing response)
- Goal achieved
- Stale thread alerts
- Security alerts (quarantined)
- Commitment detected (approval needed)
- Draft ready for review

### Don't notify:
- Newsletters, low-priority auto-categorized
- Threads with auto-reply active (unless override)
- Routine follow-ups

---

## Thread Knowledge Extraction

On GOAL_MET or ARCHIVED:
1. Extract outcomes (agreements, prices, dates, decisions)
2. Update contact profiles
3. Write to long-term memory (`memory/outcomes/`)
4. Suggest follow-up with recommended date
