# Ghost Research Feature: Batch & Input Handling Analysis

## Overview
Ghost Research is an 8-phase company research and outreach pipeline. Key distinction: **ResearchBatch** (multiple companies) vs **ResearchCampaign** (single company). Batches manage parallel/sequential company processing; campaigns are individual research pipelines.

---

## 1. Database Models

### ResearchBatch (BatchJob for mass email, NOT research batches)
**Table:** `research_batches`

```python
id: int (PK)
name: str                      # Batch name (e.g., "Q1 Outreach")
total_companies: int           # Count of companies added to batch
completed: int                 # Count finished (sent or draft_pending)
failed: int                    # Count that failed at some phase
skipped: int                   # Count manually skipped
status: str                    # pending, in_progress, paused, completed, cancelled
defaults: dict (JSONB)         # Batch-level defaults (identity, goal, language, tone, etc.)
source_file: str | None        # Path to source JSON file (optional)
created_at: datetime
updated_at: datetime | None

# Relationships
campaigns: list[ResearchCampaign]  # All campaigns in this batch
```

### ResearchCampaign (Individual company research)
**Table:** `research_campaigns`

```python
id: int (PK)
company_name: str
company_slug: str              # Filesystem-safe slug (lowercase, underscores)
country: str | None
industry: str | None
identity: str                  # Sender identity ID (default: "default")
goal: str                      # Primary outreach goal
language: str                  # Email language code (default: pt-PT)
contact_name: str | None
contact_email: str | None      # Final recipient email
contact_role: str | None
cc: str | None                 # Comma-separated CC emails
extra_context: str | None      # Free-text extra context for pipeline
email_tone: str                # direct-value, consultative, relationship-first, challenger-sale
auto_reply_mode: str           # draft-for-approval, autonomous, notify-only
max_auto_replies: int          # Max auto-reply iterations (default: 3)

# Pipeline state
status: str                    # queued, phase_1..phase_6, sending, sent, draft_pending, failed, skipped
phase: int                     # 0-6 tracking current phase
error: str | None              # Error message if failed

# Research data (accumulated)
input_data: dict (JSONB)       # Phase 1: input validation data
research_data: dict (JSONB)    # All phases: dossier, opportunities, peer_intel, value_plan, verbose_log

# Email output
email_subject: str | None      # Final email subject
email_body: str | None         # Final email body
output_dir: str | None         # /home/athena/ghostpost/research/[company_slug]/

# Linking
batch_id: int | None           # FK to ResearchBatch (if part of batch)
thread_id: int | None          # FK to Thread (if sent/draft created)
queue_position: int            # Position in batch queue (for ordering)

created_at: datetime
updated_at: datetime | None
started_at: datetime | None
completed_at: datetime | None
```

---

## 2. How Companies Are Added to Research Batches

### Option A: Single Company via API
**Endpoint:** `POST /api/research/`

```json
{
  "company_name": "Acme Corp",
  "goal": "Schedule a discovery call to discuss AI automation",
  "identity": "capitao_consulting",
  "language": "pt-PT",
  "country": "Portugal",
  "industry": "Manufacturing",
  "contact_name": "John Smith",
  "contact_email": "john@acme.com",
  "contact_role": "Operations Director",
  "cc": "manager@acme.com",
  "extra_context": "They just raised $5M in Series A",
  "email_tone": "direct-value",
  "auto_reply_mode": "draft-for-approval",
  "max_auto_replies": 3
}
```

Response: `{"campaign_id": 123, "status": "started"}`

### Option B: Batch of Companies via File + API
**Endpoint:** `POST /api/research/batch`

**Input File Format (JSON):**
```json
{
  "name": "Q1 Sales Outreach",
  "defaults": {
    "identity": "capitao_consulting",
    "language": "pt-PT",
    "email_tone": "direct-value",
    "auto_reply_mode": "draft-for-approval"
  },
  "companies": [
    {
      "company_name": "Company A",
      "goal": "Partner for AI training program",
      "country": "Portugal",
      "industry": "Education",
      "contact_name": "Alice",
      "contact_email": "alice@company-a.com"
    },
    {
      "company_name": "Company B",
      "goal": "Pilot our automation platform",
      "country": "Spain",
      "industry": "Logistics",
      "contact_name": "Bob",
      "contact_email": "bob@company-b.com",
      "language": "es"  // Override default
    }
  ]
}
```

**CLI:**
```bash
ghostpost research batch companies.json --name "Q1 Sales Outreach"
```

**Process:**
1. API creates ResearchBatch record with status="pending"
2. For each company in companies[] array:
   - Merge batch defaults + company-specific fields
   - Call `create_campaign()` with merged data
   - Set batch_id and queue_position on each campaign
3. Call `run_batch(batch_id)` in background
4. Return `{"batch_id": N, "status": "started", "total_companies": M}`

---

## 3. Input Collector Module (Phase 1)

**File:** `/home/athena/ghostpost/src/research/input_collector.py`

### Purpose
Validates inputs and generates 00_input.md — entry point for all research campaigns.

### Collected Data Per Company

```python
input_data = {
    "company_name": str,
    "company_slug": str,        # _slugify() output
    "country": str | None,
    "industry": str | None,
    "identity": str,
    "goal": str,
    "language": str,
    "contact_name": str | None,
    "contact_email": str | None,
    "contact_role": str | None,
    "email_tone": str,
    "cc": str | None,
    "extra_context": str | None,
    "auto_reply_mode": str,
    "max_auto_replies": int,
    "identity_valid": bool,     # validate_identity() result
    "collected_at": str,        # ISO 8601 timestamp
}
```

### Output File: 00_input.md
**Path:** `/home/athena/ghostpost/research/[company_slug]/00_input.md`

**Structure:**
```markdown
---
company: "Company Name"
company_slug: "company_name"
country: "Portugal"
industry: "Tech"
identity: "capitao_consulting"
goal: "Goal statement"
language: "pt-PT"
email_tone: "direct-value"
auto_reply_mode: "draft-for-approval"
max_auto_replies: 3
collected_at: "2026-02-27T14:30:45Z"
---

# Research Input: Company Name

## Target Company
- **Name:** Company Name
- **Country:** Portugal
- **Industry:** Tech

## Goal
[Goal from campaign]

## Contact
- **Name:** Contact Name or "To be researched"
- **Email:** contact@company.com or "To be researched"
- **Role:** Director of Operations or "To be researched"

## Sender Identity
- **Identity:** capitao_consulting (valid)
- **Company:** Capitao Consulting
- **Sender:** Athena Capitao

## CC Recipients
manager@company.com

## Extra Context
Context provided by user

## Email Settings
- **Language:** pt-PT
- **Tone:** direct-value
- **Auto-Reply Mode:** draft-for-approval
- **Max Auto-Replies:** 3
```

### Phase 1 Processing
1. Fetch campaign from DB
2. Set status="phase_1", phase=1, started_at=now
3. Validate identity exists via `validate_identity()`
4. Load identity details via `load_identity()`
5. Build input_data dict
6. Build 00_input.md content
7. Write atomically to `/research/[company_slug]/00_input.md`
8. Save input_data to campaign.input_data (JSONB)
9. Update campaign status to phase_2

---

## 4. Queue & Batch Processing System

**Files:**
- `src/research/queue.py` — Batch orchestration
- `src/research/pipeline.py` — Single campaign pipeline runner

### Batch State Lifecycle

```
PENDING → IN_PROGRESS → [PAUSED ↔ RESUME] → COMPLETED
                      → CANCELLED (admin action)
```

### Campaign State Lifecycle (Within Batch)

```
QUEUED → PHASE_1 → PHASE_2 → ... → PHASE_6 → SENDING
                                            → SENT (autonomous mode)
                                            → DRAFT_PENDING (draft-for-approval)
       → FAILED (any phase error, can retry)
       → SKIPPED (manual skip)
```

### Batch Processing Flow

**Function:** `async run_batch(batch_id: int) -> dict`

```python
1. Set batch.status = "in_progress"
2. Get all campaigns ordered by queue_position
3. For each campaign in sequence:
   a. Check if batch was paused (via _batch_running flag)
   b. Skip if already completed/skipped/failed
   c. Run full pipeline: await run_pipeline(campaign_id)
   d. Update batch counters:
      - completed += 1 if status in ("sent", "draft_pending")
      - failed += 1 if status == "failed"
   e. Catch exceptions, increment failed counter
4. Set batch.status = "completed" (unless paused)
5. Return batch_status dict
```

### Pause/Resume Mechanism

**In-Memory Flag:**
```python
_batch_running: dict[int, bool] = {}
```

- `pause_batch(batch_id)` → sets flag=False, keeps batch status="paused"
- `resume_batch(batch_id)` → sets status="in_progress", re-runs run_batch()

### Per-Campaign Operations

```python
await skip_campaign(campaign_id)
  # Changes status to "skipped" (if queued/failed)
  # Increments batch.skipped counter

await retry_campaign(campaign_id)
  # Resets failed campaign: status="queued", phase=0, error=None
  # (Must be re-run via run_batch or individual run_pipeline)
```

---

## 5. Pipeline Orchestration

**File:** `src/research/pipeline.py`

### Full 8-Phase Pipeline

**Function:** `async run_pipeline(campaign_id: int) -> dict`

```
Phases:
1. Phase 1: Input Collection       (input_collector.collect_input)
2. Phase 2: Deep Research          (researcher.research_company)
3. Phase 3: Opportunity Analysis   (opportunity.analyze_opportunities)
4. Phase 4: Contacts Search        (contacts_search.search_contacts)
5. Phase 5: Person Research        (person_researcher.research_person) — conditional, only when contact_name provided
6. Phase 6: Peer Intelligence      (peer_intel.gather_peer_intel)
7. Phase 7: Value Proposition      (value_plan.create_value_plan)
8. Phase 8: Email Composition      (email_writer.compose_email)

Post-Pipeline:
9. Email Delivery:
   - autonomous mode → send_new() + create_thread_from_compose()
   - draft-for-approval → create_draft() (status=draft_pending)
   - no contact_email → mark draft_pending for manual review
```

### Verbose Logging

**In:** `research_data["verbose_log"]` (list of dicts)

```python
{
  "ts": "14:30:45",          # HH:MM:SS UTC
  "phase": 1,                # 0-6
  "msg": "Starting Phase 1..."
}
```

Real-time accessible via:
- `GET /api/research/{campaign_id}` → research_data.verbose_log
- `ghostpost research status <id> --watch` polls and streams

### Output Directory Structure

```
/home/athena/ghostpost/research/[company_slug]/
├── 00_input.md                      # Phase 1 output
├── 01_company_dossier.md            # Phase 2 output
├── 02_opportunity_analysis.md       # Phase 3 output
├── 03_contacts_search.md            # Phase 4 output
├── 04b_person_profile.md            # Phase 5 output (conditional — only when contact_name provided)
├── 04_peer_intelligence.md          # Phase 6 output
├── 05_value_proposition_plan.md     # Phase 7 output
└── 06_email_draft.md                # Phase 8 output (if autonomous)
```

---

## 6. API Endpoints (Research)

### Single Campaign
```
POST   /api/research/
       Request: ResearchRequest
       Response: {"campaign_id": int, "status": "started"}

GET    /api/research/{campaign_id}
       Response: ResearchCampaignOut (with research_data)

POST   /api/research/{campaign_id}/skip
       Response: {"status": "skipped", "campaign_id": int}

POST   /api/research/{campaign_id}/retry
       Response: {"status": "retrying", "campaign_id": int}

GET    /api/research/
       Params: status=<status>, batch_id=<batch_id>, page=<int>, page_size=<int>
       Response: {"total": int, "page": int, "items": [ResearchCampaignOut, ...]}

GET    /api/research/{campaign_id}/output/{filename}
       Params: filename ∈ [00_input.md, 01_company_dossier.md, ...]
       Response: {"filename": str, "content": str}
```

### Batch Operations
```
POST   /api/research/batch
       Request: ResearchBatchRequest
       Response: {"batch_id": int, "status": "started", "total_companies": int}

GET    /api/research/batch/{batch_id}
       Response: {
         "batch_id": int,
         "name": str,
         "status": str,
         "total_companies": int,
         "completed": int,
         "failed": int,
         "skipped": int,
         "campaigns": [
           {"id": int, "company_name": str, "status": str, "phase": int, "error": str | None, ...},
           ...
         ]
       }

POST   /api/research/batch/{batch_id}/pause
       Response: {"status": "paused", "batch_id": int}

POST   /api/research/batch/{batch_id}/resume
       Response: {"status": "resumed", "batch_id": int}

GET    /api/research/batches
       Params: page=<int>, page_size=<int>
       Response: {"total": int, "page": int, "items": [ResearchBatchOut, ...]}
```

### Identities
```
GET    /api/research/identities
       Response: [{"id": str, "company_name": str, "sender_email": str, ...}, ...]

GET    /api/research/identities/{identity_id}
       Response: IdentityOut (with full metadata + body)

POST   /api/research/identities
       Request: IdentityRequest
       Response: {"id": str, "status": "created"}

PUT    /api/research/identities/{identity_id}
       Request: IdentityRequest
       Response: {"id": str, "status": "updated"}

DELETE /api/research/identities/{identity_id}
       Response: {"id": str, "status": "deleted"}
```

---

## 7. CLI Commands (Research)

```bash
# Single Company
ghostpost research run "Company Name" \
  --goal "Discover AI automation opportunities" \
  --identity "capitao_consulting" \
  --language "pt-PT" \
  --country "Portugal" \
  --industry "Tech" \
  --contact-name "John" \
  --contact-email "john@company.com" \
  --tone "direct-value" \
  --mode "draft-for-approval" \
  --watch                           # Default: on (--no-watch to skip)
  --json                            # JSON output

# Status & Progress
ghostpost research status <campaign_id> [--watch] [--json]

# List Campaigns
ghostpost research list [--status <status>] [--json]

# Batch Operations
ghostpost research batch companies.json [--name "Batch Name"] [--json]
ghostpost research queue <batch_id> [--json]
ghostpost research pause <batch_id> [--json]
ghostpost research resume <batch_id> [--json]

# Per-Campaign
ghostpost research skip <campaign_id> [--json]
ghostpost research retry <campaign_id> [--json]

# Output Files
ghostpost research output <campaign_id> <filename>
  # filename ∈ [00_input.md, 01_company_dossier.md, ...]

# Identities
ghostpost research identities [--json]
```

---

## 8. Identity System

**Location:** `/home/athena/ghostpost/config/identities/`

### Identity File Format (Markdown + Frontmatter)

**File:** `[identity_id].md`

```markdown
---
identity_id: "capitao_consulting"
company_name: "Capitao Consulting"
sender_name: "Athena Capitao"
sender_title: "Founder & AI Consultant"
sender_email: "athenacapitao@gmail.com"
website: "https://capitao.consulting"
industry: "AI Consulting"
tagline: "AI-powered transformation for forward-thinking businesses"
sender_phone: "+351 XXX XXX XXX"
sender_linkedin: "https://linkedin.com/in/athena-capitao"
calendar_link: "https://cal.com/athena"
---

# Company Overview
Capitao Consulting is a Portugal-based AI consulting firm...

# Services & Products
- AI Agent Deployment
- AI Strategy & Roadmapping
- Custom AI Solutions
...
```

### Required Fields
- identity_id
- company_name
- sender_name
- sender_email
- sender_title

### Optional Fields
- website
- industry
- tagline
- sender_phone
- sender_linkedin
- calendar_link
- created
- last_updated

### API/CLI Operations
```python
list_identities() → list[str]
  # Returns identity IDs (filenames without .md, excluding _template)

load_identity(name: str) → dict
  # Parses frontmatter, returns all fields + "body"

validate_identity(name: str) → (bool, list[str])
  # Returns (is_valid, missing_fields)

save_identity(name: str, metadata: dict, body: str) → Path
  # Saves identity file (creates if not exists, overwrites if exists)

get_identity_context(name: str) → str
  # Formats identity for LLM prompt inclusion
```

---

## 9. Request/Response Schemas

### ResearchRequest (Single Campaign)
```python
company_name: str (required)
goal: str (required)
identity: str = "default"
language: str = "pt-PT"
country: str | None = None
industry: str | None = None
contact_name: str | None = None
contact_email: str | None = None
contact_role: str | None = None
cc: str | None = None              # Comma-separated emails
extra_context: str | None = None   # Max 10,000 chars
email_tone: str = "direct-value"
auto_reply_mode: str = "draft-for-approval"
max_auto_replies: int = 3

Validators:
- identity: alphanumeric + hyphens + underscores only
- cc: valid email addresses (if provided)
```

### ResearchBatchRequest
```python
name: str (required)              # Batch name
companies: list[dict] (required)  # Array of company objects
defaults: dict | None = None      # Batch-level defaults

# Each company in companies[] is a dict with:
#   company_name (required)
#   goal (required)
#   identity, language, country, industry, contact_name, contact_email, etc. (optional)
#   (Merged with batch defaults; company values override)
```

### ResearchCampaignOut
```python
id: int
company_name: str
company_slug: str
country: str | None
industry: str | None
identity: str
goal: str
language: str
contact_name: str | None
contact_email: str | None
cc: str | None
extra_context: str | None
status: str
phase: int
error: str | None
email_subject: str | None
output_dir: str | None
batch_id: int | None
thread_id: int | None
queue_position: int
research_data: dict | None          # JSONB: {verbose_log, completed_phases, ...}
created_at: datetime
started_at: datetime | None
completed_at: datetime | None
```

### ResearchBatchOut
```python
id: int
name: str
total_companies: int
completed: int
failed: int
skipped: int
status: str
created_at: datetime
```

---

## 10. Defaults & Configuration

**File:** `/home/athena/ghostpost/config/ghost_research_defaults.md`

```yaml
default_language: "pt-PT"
default_email_tone: "direct-value"
default_auto_reply_mode: "draft-for-approval"
default_max_auto_replies: 3
default_max_email_length: 150
default_include_meeting_request: false
default_include_case_study: false
default_follow_up_days: 3
```

### Email Tones
- **direct-value:** Bold, ROI-focused, leads with numbers
- **consultative:** Deep understanding, leads with insight
- **relationship-first:** Warm, personal, connection-focused
- **challenger-sale:** Provocative, challenges assumptions

### Auto-Reply Modes
- **draft-for-approval:** Agent drafts, human approves (DEFAULT)
- **autonomous:** Agent responds automatically
- **notify-only:** Agent alerts, takes no action

---

## 11. Data Flow Summary

### Single Campaign Flow
```
POST /api/research/
  ↓
create_campaign()
  ↓
ResearchCampaign(status=queued, phase=0)
  ↓
run_pipeline(campaign_id) [background]
  ├─ Phase 1: collect_input() → 00_input.md
  ├─ Phase 2: research_company() → 01_company_dossier.md
  ├─ Phase 3: analyze_opportunities() → 02_opportunity_analysis.md
  ├─ Phase 4: search_contacts() → 03_contacts_search.md + update contact_email
  ├─ Phase 5: research_person() → 04b_person_profile.md (conditional)
  ├─ Phase 6: gather_peer_intel() → 04_peer_intelligence.md
  ├─ Phase 7: create_value_plan() → 05_value_proposition_plan.md
  └─ Phase 8: compose_email() → email_subject, email_body, 06_email_draft.md
  ↓
  If autonomous: send_new() + create_thread()
  If draft: create_draft()
  ↓
  campaign.status = "sent" | "draft_pending" | "failed"
```

### Batch Flow
```
POST /api/research/batch (companies.json)
  ↓
create_batch()
  └─ ResearchBatch(status=pending)
  └─ For each company:
     └─ create_campaign(batch_id=X, queue_position=i)
  ↓
run_batch(batch_id) [background]
  ├─ Set batch.status = "in_progress"
  └─ For each campaign (ordered by queue_position):
     ├─ Check _batch_running flag (pause support)
     ├─ run_pipeline(campaign_id)
     └─ Update batch counters: completed/failed/skipped
  ↓
  batch.status = "completed" (unless paused)
```

---

## 12. Batch File Format Example

```json
{
  "name": "February 2026 AI Outreach",
  "defaults": {
    "identity": "capitao_consulting",
    "language": "pt-PT",
    "email_tone": "direct-value",
    "auto_reply_mode": "draft-for-approval",
    "max_auto_replies": 3
  },
  "companies": [
    {
      "company_name": "TechCorp Portugal",
      "goal": "Introduce AI agent deployment services",
      "country": "Portugal",
      "industry": "SaaS",
      "contact_name": "Maria Silva",
      "contact_email": "maria@techcorp.pt",
      "contact_role": "CTO"
    },
    {
      "company_name": "Manufacturing Solutions Spain",
      "goal": "Pilot automation for production lines",
      "country": "Spain",
      "industry": "Manufacturing",
      "contact_name": "Carlos Rodriguez",
      "contact_email": "carlos@manuf-solutions.es",
      "contact_role": "Operations Manager",
      "language": "es",
      "cc": "manager@manuf-solutions.es"
    },
    {
      "company_name": "Startup Lisbon",
      "goal": "Emergency AI consulting for pivoting product",
      "country": "Portugal",
      "industry": "FinTech",
      "contact_email": "founders@startup-lisbon.pt",
      "extra_context": "They just lost their AI engineer; urgent need"
    }
  ]
}
```

---

## Key Implementation Details

### Atomic Writes
All file writes use temp + rename pattern:
```python
fd, tmp_path = tempfile.mkstemp(dir=dir_name)
# write content
os.replace(tmp_path, path)  # atomic
```

### Company Slug Generation
```python
def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)      # Remove special chars
    slug = re.sub(r'[\s_-]+', '_', slug)      # Normalize spaces/underscores
    return slug.strip('_')
    # "Tech Corp!" → "tech_corp"
```

### Queue Position Ordering
Campaigns processed sequentially by queue_position (0, 1, 2, ...). If added later to batch, queue_position is set at creation time. No automatic reordering.

### Pause/Resume Mechanism
- Global in-memory flag `_batch_running[batch_id]`
- Checked at each campaign boundary (between campaigns, not mid-phase)
- Paused campaign can be resumed; continues from next campaign

### Error Handling
- Any phase failure → campaign.status = "failed", campaign.error = error message
- Batch continues to next campaign (doesn't cascade fail)
- Can retry failed campaigns: `retry_campaign()` resets to queued

### Research Data JSONB Structure
```python
research_data = {
    "verbose_log": [
        {"ts": "HH:MM:SS", "phase": 1, "msg": "..."},
        ...
    ],
    "completed_phases": {
        "1": {"name": "Phase 1...", "completed_at": "2026-02-27T14:30:45Z"},
        ...
    },
    "phase_started_at": "2026-02-27T14:30:45Z",
    "current_phase_name": "Phase 2: Deep Research",
    # Plus phase-specific data from each phase module
}
```

