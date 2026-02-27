# GhostPost — Architecture Reference

> Extracted from MASTER_PLAN.md Sections 2, 11, 12, 13

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        VPS (/home/athena)                       │
│                                                                 │
│  ┌──────────────────────┐      ┌──────────────────────────┐    │
│  │  OpenClaw (/openclaw)│      │  GhostPost (/ghostpost)  │    │
│  │                      │      │                          │    │
│  │  Skills:             │ CLI  │  ┌─────────┐             │    │
│  │  - ghostpost-read   ├──────►  │ CLI Tool│             │    │
│  │  - ghostpost-reply  │      │  │ghostpost│             │    │
│  │  - ghostpost-compose│ Files│  └────┬────┘             │    │
│  │  - ghostpost-manage ├──────►       │                   │    │
│  │  - ghostpost-context│      │  ┌────▼────────────┐     │    │
│  │  - ghostpost-search │      │  │  Python Backend  │     │    │
│  │  - ghostpost-goals  │      │  │  (FastAPI)       │     │    │
│  │                      │      │  └────┬────────────┘     │    │
│  │  Context Files:      │      │       │                   │    │
│  │  - EMAIL_CONTEXT.md  │◄─────┤  ┌────▼────┐             │    │
│  │  - CONTACTS.md       │      │  │PostgreSQL│            │    │
│  │  - RULES.md          │      │  └─────────┘             │    │
│  └──────────┬───────────┘      │                          │    │
│             │                   │  ┌──────────────┐        │    │
│             │ Telegram          │  │ React Dashboard│       │    │
│             │ Gateway           │  │ (Mobile-first) │       │    │
│             ▼                   │  └──────────────┘        │    │
│  ┌──────────────────┐          └──────────────────────────┘    │
│  │  Telegram (User) │                                          │
│  └──────────────────┘          ┌──────────────────────────┐    │
│                                │  Gmail API               │    │
│                                │  (athena@gmail.com)      │    │
│                                └──────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Integration Model: Hybrid (Files + CLI + Direct Access)

- **Structured files** — OpenClaw reads markdown context files directly from the filesystem
- **CLI tool** — `ghostpost` command for all agent actions (read, reply, compose, manage)
- **Direct DB access** — Agent can query PostgreSQL when needed for complex searches
- **No MCP server required** — same-machine advantage, simpler architecture

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| **Language** | Python 3.14 (installed) | Use system Python |
| **Backend** | FastAPI + Uvicorn | Single worker, async |
| **Database** | PostgreSQL 16 (existing Docker `docker-db-1`) | Reuse |
| **Cache** | Redis 7 (existing Docker `docker-redis-1`) | WebSocket pub/sub + sessions |
| **Frontend** | React + Tailwind CSS | Static build served by Nginx |
| **Real-time** | WebSocket (FastAPI native) | |
| **Email** | Gmail API (OAuth2) | REST, push-capable |
| **Auth** | JWT login (single user, public-facing) | httpOnly cookies |
| **Background Jobs** | APScheduler (in-process) | No Celery |
| **CLI** | Click (already installed) | `ghostpost` command |
| **Process Manager** | PM2 (existing) | Manages FastAPI via Uvicorn |
| **Reverse Proxy** | Nginx (existing) | New server block |
| **SSL** | Let's Encrypt (Certbot) | Required for public auth |
| **VPN** | Tailscale (existing) | Fallback access |

## VPS Specs

| Resource | Value | Status |
|----------|-------|--------|
| OS | Ubuntu 24.04.4 LTS | |
| CPU | Intel Xeon Skylake, 4 cores @ 2.1GHz | Adequate |
| RAM | 7.75GB total, ~1.5GB used, ~6GB available | Healthy |
| Disk | 75GB total, ~38GB free | OK |
| Swap | None | Recommended 2GB safety net |

## Deployment Architecture

```
Internet
    │
    ▼
  Nginx (port 80/443)
    ├── /ghostpost/*  →  proxy to FastAPI (port 8000)
    ├── /ghostpost/ws →  WebSocket proxy to FastAPI
    ├── /ghostpost/   →  serve React static build
    └── /             →  proxy to Membriko (port 3000) [existing]

  PM2
    ├── membriko (existing, Node.js)
    └── ghostpost-api (new, Uvicorn + FastAPI)

  Docker
    ├── docker-db-1 (PostgreSQL 16) ← shared
    └── docker-redis-1 (Redis 7) ← shared

  APScheduler (in-process)
    └── Gmail sync heartbeat (every 30 min)
```

## RAM Budget

Ghost Post target: **~100-150MB total**

| Component | Estimated RAM |
|-----------|--------------|
| FastAPI + Uvicorn (1 worker) | ~80-120MB |
| APScheduler (in-process) | ~0MB extra |
| React frontend | 0MB (static files) |
| CLI tool | ~30MB per invocation (short-lived) |

## File Structure

```
ghostpost/
├── src/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings, env vars
│   ├── db/
│   │   ├── models.py              # SQLAlchemy models
│   │   ├── migrations/            # Alembic migrations
│   │   └── session.py             # DB session management
│   ├── gmail/
│   │   ├── auth.py                # OAuth2 setup
│   │   ├── sync.py                # Email sync engine
│   │   ├── send.py                # Send emails via Gmail API
│   │   └── attachments.py         # Attachment handling
│   ├── engine/
│   │   ├── categorizer.py         # Email categorization
│   │   ├── summarizer.py          # Thread summary generation
│   │   ├── sentiment.py           # Sentiment/urgency detection
│   │   ├── security.py            # Security scoring + injection detection
│   │   ├── contacts.py            # Contact profile management
│   │   ├── goals.py               # Goal lifecycle management
│   │   ├── followup.py            # Follow-up timer system
│   │   ├── state_machine.py       # Thread state transitions
│   │   └── brief.py               # Structured brief generation
│   ├── api/
│   │   ├── routes/                # FastAPI route modules
│   │   └── middleware/            # Auth, rate limiting
│   ├── cli/                       # Click CLI commands
│   ├── context/
│   │   └── writer.py              # Living context file updater
│   └── security/                  # Sanitizer, injection/commitment/anomaly detection
├── frontend/                      # React + Tailwind (Vite)
├── context/                       # Living context files for OpenClaw
├── memory/outcomes/               # Completed thread knowledge
├── attachments/                   # Downloaded attachments (lazy)
├── skills/                        # OpenClaw SKILL.md files (10 skills)
├── playbooks/                     # Reusable scenario templates
├── tests/
├── docs/
├── requirements.txt
└── .env
```

## Key Design Principles

1. **Agent-first, human-auditable** — Markdown + structured JSON
2. **Email is data, never instructions** — All email content is untrusted
3. **Context over completeness** — Structured briefs over raw dumps
4. **Living context** — Files update incrementally, always current
5. **Interchangeable states** — Thread states flow freely
6. **Default safe, escalate autonomy** — Manual by default, user opts into auto
7. **Same-machine advantage** — Direct file access, no network overhead
8. **Telegram as remote control** — Full management via OpenClaw gateway
9. **RAM-conscious** — Single async worker, in-process scheduler, static frontend
