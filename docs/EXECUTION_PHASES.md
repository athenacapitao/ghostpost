# GhostPost — Execution Phases

> Extracted from MASTER_PLAN.md Sections 10, 12.8

---

## Phase 0 — Infrastructure Setup
**Goal:** VPS ready for Ghost Post development

- [ ] Configure 2GB swap file on VPS
- [ ] Create `ghostpost` database in existing PostgreSQL container
- [ ] Create `ghostpost` user with scoped permissions
- [ ] Set up Gmail API project in Google Cloud Console
- [ ] Generate OAuth2 credentials for Gmail API
- [ ] Set up Nginx server block for Ghost Post (with SSL)
- [ ] Create `.env` file with all secrets (DB, Gmail, JWT)
- [ ] Set up PM2 ecosystem config for `ghostpost-api`
- [ ] Install Python dependencies in a virtualenv
- [ ] Scaffold React frontend with Vite + Tailwind
- [ ] Verify end-to-end: Nginx → FastAPI → PostgreSQL → Redis

---

## Phase 1 — Foundation (MVP)
**Goal:** Email mirror working, basic dashboard, agent can read emails
**Depends on:** Phase 0

- [ ] Gmail API integration (OAuth2 setup, 30-min sync heartbeat via APScheduler)
- [ ] PostgreSQL schema creation and migrations (Alembic)
- [ ] Email sync engine — import all historical emails
- [ ] Thread grouping from Gmail API native threads
- [ ] Store all email fields (from, to, cc, bcc, date, headers, etc.)
- [ ] Attachment metadata storage + lazy download
- [ ] Basic CLI tool: `ghostpost threads`, `ghostpost thread <id>`, `ghostpost email <id>`, `ghostpost search`, `ghostpost sync`, `ghostpost stats`
- [ ] FastAPI backend serving email/thread data
- [ ] React dashboard: login, thread list, thread detail (side-by-side layout)
- [ ] WebSocket for real-time thread list updates
- [ ] Dark mode, mobile-first responsive design
- [ ] Storage monitoring indicator in dashboard

---

## Phase 2 — Agent Intelligence
**Goal:** Agent can categorize, summarize, and enrich data

- [ ] Background categorization job (first email per thread)
- [ ] Thread summary generation (on each new email)
- [ ] Sentiment, urgency, action-required detection per email
- [ ] Priority auto-scoring per thread
- [ ] Contact profile builder (from email history)
- [ ] Security scoring engine (0-100 per email/thread)
- [ ] Living context files: EMAIL_CONTEXT.md, CONTACTS.md, RULES.md, ACTIVE_GOALS.md
- [ ] Context file incremental update system
- [ ] Structured brief generation for threads

---

## Phase 3 — Agent Actions
**Goal:** Agent can reply, compose, and manage threads

- [ ] Reply system: `ghostpost reply`, `ghostpost draft`
- [ ] Compose system: `ghostpost compose`
- [ ] Draft review queue (dashboard + context files)
- [ ] Thread state machine with transitions
- [ ] Auto-reply toggle per thread (dashboard UI)
- [ ] Follow-up system (default 3 days, per-thread override)
- [ ] Goal/acceptance criteria fields (dashboard + CLI)
- [ ] Multi-goal support (sequential goals per thread)
- [ ] Playbook system (markdown templates, dashboard selector)

---

## Phase 4 — Security & Safety
**Goal:** Production-grade protection

- [ ] Prompt injection detection (6-layer defense)
- [ ] Input sanitization layer for email content
- [ ] Content isolation wrapping
- [ ] Commitment detection engine
- [ ] Anomaly detection on agent actions
- [ ] Quarantine mode (dashboard + CLI)
- [ ] Recipient blocklist + "never auto-reply" list
- [ ] Sensitive topic detection (legal, financial, personal)
- [ ] Rate limiting on agent-sent emails
- [ ] Full audit log (every agent action)

---

## Phase 5 — OpenClaw Skills
**Goal:** Full skill suite installed and tested

- [ ] `ghostpost-read` skill
- [ ] `ghostpost-reply` skill
- [ ] `ghostpost-compose` skill
- [ ] `ghostpost-manage` skill
- [ ] `ghostpost-context` skill
- [ ] `ghostpost-search` skill
- [ ] `ghostpost-goals` skill
- [ ] `ghostpost-playbook` skill
- [ ] `ghostpost-security` skill
- [ ] `ghostpost-notify` skill
- [ ] Reference docs for each skill
- [ ] Integration tests: Telegram → OpenClaw → Ghost Post → Gmail

---

## Phase 6 — Advanced Features
**Goal:** Contact enrichment, knowledge extraction, polish

- [ ] Contact enrichment via web search (OpenClaw native)
- [ ] Proxycurl integration (optional, for LinkedIn data)
- [ ] Thread knowledge extraction on completion
- [ ] Long-term memory system (outcome files)
- [ ] Smart notification filtering engine
- [ ] Dashboard overview/stats page
- [ ] Settings page (reply style, defaults, blocklists, thresholds)
- [ ] Playbook creation from dashboard
- [ ] Reply style configuration (formal default, user-changeable)
- [ ] Notification granularity controls
