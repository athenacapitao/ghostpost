# GhostPost — Database Schema Reference

> Extracted from MASTER_PLAN.md Section 8

---

## Connection

```
PostgreSQL 16 (Docker container: docker-db-1)
Database: ghostpost
Connection: postgresql://ghostpost:PASSWORD@localhost:5432/ghostpost
Max pool: 10 connections
```

---

## Tables

### emails
```
id                  SERIAL PRIMARY KEY
gmail_id            VARCHAR UNIQUE
thread_id           FK → threads.id
message_id          VARCHAR (RFC 2822 Message-ID)
from_address        VARCHAR
to_addresses        JSONB
cc                  JSONB
bcc                 JSONB
subject             TEXT
body_plain          TEXT
body_html           TEXT
date                TIMESTAMPTZ
received_at         TIMESTAMPTZ
headers             JSONB
attachment_metadata JSONB
security_score      INTEGER (0-100)
sentiment           VARCHAR (positive/neutral/negative/frustrated)
urgency             VARCHAR (low/medium/high/critical)
action_required     JSONB (yes/no + description)
is_read             BOOLEAN
is_sent             BOOLEAN
is_draft            BOOLEAN
created_at          TIMESTAMPTZ DEFAULT NOW()
```

### threads
```
id                  SERIAL PRIMARY KEY
gmail_thread_id     VARCHAR UNIQUE
subject             TEXT
category            VARCHAR (agent-invented freeform)
summary             TEXT
state               VARCHAR (NEW/ACTIVE/WAITING_REPLY/FOLLOW_UP/GOAL_MET/ARCHIVED)
priority            VARCHAR (low/medium/high/critical)
auto_reply_mode     VARCHAR (auto/manual/off) DEFAULT 'off'
follow_up_days      INTEGER DEFAULT 3
next_follow_up_date TIMESTAMPTZ
playbook_id         FK → playbooks.id (nullable)
notes               TEXT
security_score_avg  INTEGER
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ
last_activity_at    TIMESTAMPTZ
```

### contacts
```
id                      SERIAL PRIMARY KEY
email                   VARCHAR UNIQUE
name                    VARCHAR
aliases                 JSONB
relationship_type       VARCHAR (client/vendor/friend/colleague/unknown)
communication_frequency VARCHAR (daily/weekly/monthly/rare)
avg_response_time       INTERVAL
preferred_style         VARCHAR (brief/detailed/formal/casual)
topics                  JSONB
notes                   TEXT
enrichment_source       VARCHAR (email_history/web_search/proxycurl)
last_interaction        TIMESTAMPTZ
created_at              TIMESTAMPTZ DEFAULT NOW()
updated_at              TIMESTAMPTZ
```

### attachments
```
id                  SERIAL PRIMARY KEY
email_id            FK → emails.id
filename            VARCHAR
content_type        VARCHAR
size                BIGINT
storage_path        VARCHAR (local file path, nullable until downloaded)
gmail_attachment_id VARCHAR (for lazy download)
created_at          TIMESTAMPTZ DEFAULT NOW()
```

### goals
```
id                  SERIAL PRIMARY KEY
thread_id           FK → threads.id
goal_text           TEXT
acceptance_criteria TEXT
status              VARCHAR (pending/in_progress/achieved/failed)
follow_up_suggestion TEXT
sequence_order      INTEGER (for multi-goal threads)
created_at          TIMESTAMPTZ DEFAULT NOW()
completed_at        TIMESTAMPTZ
```

### playbooks
```
id                  SERIAL PRIMARY KEY
name                VARCHAR UNIQUE
description         TEXT
file_path           VARCHAR (path to markdown template)
created_at          TIMESTAMPTZ DEFAULT NOW()
updated_at          TIMESTAMPTZ
```

### audit_log
```
id                  SERIAL PRIMARY KEY
timestamp           TIMESTAMPTZ DEFAULT NOW()
action_type         VARCHAR (reply_sent/draft_created/goal_updated/...)
thread_id           FK → threads.id (nullable)
email_id            FK → emails.id (nullable)
agent_reasoning     TEXT
metadata            JSONB
```

### security_events
```
id                  SERIAL PRIMARY KEY
timestamp           TIMESTAMPTZ DEFAULT NOW()
email_id            FK → emails.id (nullable)
thread_id           FK → threads.id (nullable)
event_type          VARCHAR (injection_detected/low_score/anomaly/...)
severity            VARCHAR (low/medium/high/critical)
details             TEXT
resolution          TEXT
quarantined         BOOLEAN DEFAULT FALSE
```

### settings
```
key                 VARCHAR PRIMARY KEY
value               JSONB
updated_at          TIMESTAMPTZ DEFAULT NOW()
```

Default settings: `reply_style`, `default_follow_up_days`, `commitment_threshold`, `rate_limit_per_hour`, etc.

---

## Attachment Strategy

- **Metadata** stored in PostgreSQL
- **Files** stored at `/home/athena/ghostpost/attachments/<thread_id>/<filename>`
- **Lazy download** — fetch from Gmail only when requested
- Agent accesses via file path (same machine)
- Dashboard shows metadata + download button

## Storage Monitoring

Dashboard shows: total DB size, attachment disk usage, email count, growth rate. Alerts on configurable threshold.
