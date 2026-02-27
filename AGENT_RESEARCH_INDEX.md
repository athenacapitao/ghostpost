# GhostPost Agent Research Index

**Date:** 2026-02-25  
**Researcher:** Claude Code Explorer (Haiku)  
**Scope:** Complete agent-facing architecture analysis

---

## Documents

This research produced three documents:

### 1. AGENT_QUICK_REFERENCE.md
**For:** Immediate practical use  
**Length:** 7 KB / ~200 lines  
**Contains:**
- Where to start (context files)
- 5 common workflows with copy-paste examples
- API endpoint reference
- Error handling guide
- Thread states, security scoring, debugging

**Start here if you want:** To use GhostPost from OpenClaw right now

### 2. AGENT_ARCHITECTURE.md
**For:** Complete understanding of the system  
**Length:** 24 KB / ~500 lines  
**Contains:**
- Skills framework structure (Ghost Research SKILL.md)
- 10 context files with exact fields and update triggers
- 43 CLI commands organized by group
- 73 API endpoints across 19 modules
- Configuration system and environment variables
- 4 integration patterns (context files, CLI, API, direct file reads)
- 10 pain points with suggested fixes
- Architecture strengths and recommended improvements
- Skills framework template for extending GhostPost

**Start here if you want:** To understand how everything works

### 3. AGENT_RESEARCH_INDEX.md (this file)
**For:** Navigation and high-level summary  
**Contains:** Pointer to other documents and key findings

---

## Key Findings

### Three Layers of Agent Interaction

1. **Context Files** (highest priority for agents)
   - 10 markdown files in `/home/athena/ghostpost/context/`
   - Atomic writes (never partial)
   - Auto-updated on sync
   - Read-only, no API needed
   - Examples: SYSTEM_BRIEF.md, EMAIL_CONTEXT.md, ACTIVE_GOALS.md

2. **CLI Commands** (second priority)
   - 43 commands via `ghostpost` base
   - All support `--json` for structured output
   - Examples: `ghostpost thread 42 --json`, `ghostpost research run ...`

3. **REST API** (third priority, for complex operations)
   - 73 endpoints via FastAPI
   - JWT auth via X-API-Key header
   - Examples: `GET /api/threads`, `POST /api/research/`, `POST /api/drafts/{id}/approve`

### Why This Hierarchy?

Agents should follow this priority:
1. Read context files first (atomic, instant, no latency)
2. Use CLI for operations (simpler than HTTP, JSON output)
3. Use API only for complex flows or bulk operations

### Critical Design Pattern: Atomic Writes

All context files use this pattern:
```python
fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
with os.fdopen(fd, "w") as f:
    f.write(content)  # Write to temp
os.replace(tmp_path, path)  # Atomic rename
```

**Why this matters:** Agents reading files while GhostPost updates won't see partial/corrupted files.

---

## Most Important Sections

If you only read AGENT_ARCHITECTURE.md, read these sections:

1. **Section 2: Context Files** — What files exist, what they contain, when they update
2. **Section 3: CLI Interface** — All 43 commands by group with examples
3. **Section 6: Integration Points** — How OpenClaw actually uses GhostPost
4. **Section 7: Pain Points** — What's missing that would help agents
5. **Section 8: Architecture Strengths** — What GhostPost does really well

---

## For Different Roles

### OpenClaw Agent Developer
1. Read AGENT_QUICK_REFERENCE.md (practical examples)
2. Read AGENT_ARCHITECTURE.md Section 2 (context files)
3. Read AGENT_ARCHITECTURE.md Section 6 (integration patterns)
4. Bookmark API endpoint reference in AGENT_ARCHITECTURE.md Section 4

### GhostPost Backend Developer
1. Read AGENT_ARCHITECTURE.md Section 1 (skills framework)
2. Read AGENT_ARCHITECTURE.md Section 7 (pain points — these are feature requests)
3. Read AGENT_ARCHITECTURE.md Section 9 (recommended improvements)
4. Use skills template in AGENT_ARCHITECTURE.md Section 10 for new features

### DevOps / Infrastructure
1. Read AGENT_ARCHITECTURE.md Section 5 (configuration)
2. Check environment variables section
3. Look at context file write pattern (atomic, safe)

### Product / Research
1. Read this index
2. Skim AGENT_QUICK_REFERENCE.md (use cases)
3. Read AGENT_ARCHITECTURE.md Section 7 (pain points) and Section 9 (improvements)

---

## Quick Facts

| Metric | Value |
|--------|-------|
| Total API Endpoints | 73 |
| Total CLI Commands | 43 |
| Context Files | 10 |
| Skills Implemented | 1 (Ghost Research) |
| Skill Endpoints | 12 |
| Python LOC (Backend) | 6,770 |
| Database Models | 13 tables |
| Route Modules | 19 |
| Largest Module | threads.py (325 LOC) |
| Context File Generator | context_writer.py (977 LOC) |

---

## Critical Configuration

In `.env`:
```bash
ADMIN_USERNAME=athena
ADMIN_PASSWORD=<hash>
MINIMAX_API_KEY=<for LLM>
SEARCH_API_KEY=<for web research>
GMAIL_OAUTH_TOKEN_FILE=token.json
REDIS_URL=redis://localhost:6379/1
DATABASE_URL=postgresql://contawise@localhost/ghostpost
```

Context files live at: `/home/athena/ghostpost/context/`  
Research output: `/home/athena/ghostpost/research/[company_slug]/`  
Skill definitions: `/home/athena/ghostpost/skills/*/SKILL.md`

---

## The Agent-First Philosophy

GhostPost is designed with agents as the primary user:

1. **Structured output** — All responses are JSON or markdown, never free-form text
2. **Hierarchical context** — Big picture first (SYSTEM_BRIEF), then list (EMAIL_CONTEXT), then details (threads/*.md)
3. **Atomic operations** — Context files never partial, all writes are atomic
4. **Explicit errors** — Error codes distinguish retryable vs permanent failures
5. **Safe by default** — Drafts require approval, low security scores block auto-reply, untrusted email isolated

---

## Next Action

If integrating OpenClaw with GhostPost:

1. Read AGENT_QUICK_REFERENCE.md cover to cover (10 minutes)
2. Try one workflow from section "Common Workflows" (5 minutes)
3. Reference AGENT_ARCHITECTURE.md as needed for specifics

If implementing new features in GhostPost:

1. Read AGENT_ARCHITECTURE.md Section 7 (pain points) for context
2. Check Section 9 (improvements) for precedence
3. Use skills template (Section 10) for architecture
4. Ensure all new features support `--json` in CLI and return structured JSON in API

---

**Generated:** 2026-02-25  
**By:** Claude Code Explorer (Haiku model)  
**Research depth:** Thorough (all agent-facing surfaces)
