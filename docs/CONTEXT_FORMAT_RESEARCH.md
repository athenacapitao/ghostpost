# Context File Format Analysis: GhostPost & OpenClaw

## Executive Summary

**Current State:**
- GhostPost context files use **HTML comments** for schema versioning (`<!-- schema_version: 1 -->`)
- Identity files and research outputs use **YAML frontmatter** (`---` delimited blocks)
- OpenClaw has **robust YAML frontmatter parsing** with fallback to line-based parsing
- Adding YAML frontmatter to GhostPost context files is **100% compatible** with existing parsers

**Recommendation:** Migrate GhostPost context files from HTML comment versioning to YAML frontmatter for consistency with identity files and OpenClaw patterns.

---

## GhostPost Context Files (Current Format)

### Files & Pattern

All 9 context files in `/home/athena/ghostpost/context/` follow the same pattern:

| File | Line 1 | Line 2 | Current Schema |
|------|--------|--------|---|
| SYSTEM_BRIEF.md | `# System Brief` | `<!-- schema_version: 1 -->` | HTML comment |
| EMAIL_CONTEXT.md | `# Email Context` | `<!-- schema_version: 1 -->` | HTML comment |
| CONTACTS.md | `# Contacts` | `<!-- schema_version: 1 -->` | HTML comment |
| RULES.md | `# Rules & Settings` | `<!-- schema_version: 1 -->` | HTML comment |
| ACTIVE_GOALS.md | `# Active Goals` | `<!-- schema_version: 1 -->` | HTML comment |
| DRAFTS.md | `# Pending Drafts` | `<!-- schema_version: 1 -->` | HTML comment |
| SECURITY_ALERTS.md | `# Security Alerts` | `<!-- schema_version: 1 -->` | HTML comment |
| RESEARCH.md | `# Ghost Research` | `<!-- schema_version: 1 -->` | HTML comment |
| ALERTS.md | `# Active Alerts` | `<!-- schema_version: 1 -->` | HTML comment |

### Generation Code
Location: `/home/athena/ghostpost/src/engine/context_writer.py` + `/home/athena/ghostpost/src/engine/notifications.py`

All 9 context files are built as string arrays and written atomically:
```python
lines = [
    "# System Brief",
    "<!-- schema_version: 1 -->",
    f"_Generated: {now_str}_",
    ...
]
content = "\n".join(lines) + "\n"
_atomic_write(path, content)
```

**Atomic write pattern:** Uses tempfile + `os.replace()` to prevent partial reads.

### Current Schema Version Usage
- **Single version across all files:** `1`
- **No parsing of schema version in code** — it's purely informational
- **No conditional behavior** based on version
- **Purpose:** Document format stability for external tools/agents reading context

---

## GhostPost Identity Files (YAML Frontmatter)

### Location
`/home/athena/ghostpost/config/identities/*.md`

### Format Example
```yaml
---
identity_id: "capitao_consulting"
company_name: "Capitao Consulting"
website: "https://capitao.consulting"
industry: "AI Consulting & Technology"
tagline: "AI-powered transformation for forward-thinking businesses"
sender_name: "Athena Capitao"
sender_title: "Founder & AI Consultant"
sender_email: "athenacapitao@gmail.com"
sender_phone: ""
sender_linkedin: ""
calendar_link: ""
created: "2026-02-25"
last_updated: "2026-02-25"
---

# Company Overview
[markdown body...]
```

### Parsing Code
Location: `/home/athena/ghostpost/src/research/identities.py`

**Custom YAML parser (lines 13-41):**
```python
def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file.
    
    Returns (metadata_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content
    
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    
    metadata: dict = {}
    for line in parts[1].strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Handle booleans
            if value.lower() == "true":
                metadata[key] = True
            elif value.lower() == "false":
                metadata[key] = False
            else:
                metadata[key] = value
    
    body = parts[2].strip()
    return metadata, body
```

**Characteristics:**
- Splits on `---` delimiter
- Parses YAML as simple `key: value` lines
- Strips quotes from values
- Handles booleans
- Returns metadata dict + body text separately
- **No external YAML library** — manual line-by-line parsing

### Saving Code (lines 139-165)
Also custom: rebuilds frontmatter from dict, quotes string values, quotes list values.

---

## GhostPost Research Output Files

### Location
`/home/athena/ghostpost/research/[company_slug]/00-dossier.md` (and others)

### Format Example (from researcher.py, lines 206-213)
```python
full_content = f"""---
company: "{company}"
research_date: "{now}"
sources_consulted: {len(sources)}
confidence_level: "{confidence}"
---

{dossier_content}
"""
```

**Frontmatter fields:**
- `company`: string
- `research_date`: ISO datetime string
- `sources_consulted`: integer
- `confidence_level`: string ("high", "medium", "low")

---

## GhostPost SKILL.md Format

### Location
`/home/athena/ghostpost/skills/ghost-research/SKILL.md`

### Format (lines 1-5)
```yaml
---
name: ghost-research
description: Deep company research pipeline...
user-invocable: true
---

# Ghost Research Skill
```

**Fields:**
- `name`: string
- `description`: string (can be multiline with `|`)
- `user-invocable`: boolean

---

## OpenClaw Frontmatter Parsing

### Files
- `/home/athena/openclaw/src/markdown/frontmatter.ts` — Core parser
- `/home/athena/openclaw/src/shared/frontmatter.ts` — Schema utilities
- `/home/athena/openclaw/src/agents/skills/frontmatter.ts` — Skill-specific parsing

### How It Works

**Two-phase parsing** (frontmatter.ts, lines 133-157):
1. **YAML parser** — Uses `YAML.parse()` from npm `yaml` package
2. **Fallback line parser** — If YAML fails, parses `key: value` lines
3. **Merge** — Combines both, prioritizing YAML-valid keys

```typescript
export function parseFrontmatterBlock(content: string): ParsedFrontmatter {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!normalized.startsWith("---")) {
    return {};
  }
  const endIndex = normalized.indexOf("\n---", 3);
  if (endIndex === -1) {
    return {};
  }
  const block = normalized.slice(4, endIndex);
  
  const lineParsed = parseLineFrontmatter(block);
  const yamlParsed = parseYamlFrontmatter(block);
  if (yamlParsed === null) {
    return lineParsed;
  }
  
  const merged: ParsedFrontmatter = { ...yamlParsed };
  for (const [key, value] of Object.entries(lineParsed)) {
    if (value.startsWith("{") || value.startsWith("[")) {
      merged[key] = value;
    }
  }
  return merged;
}
```

**Features:**
- **Handles `---` delimited blocks** between lines 1-2 and end
- **Supports YAML syntax** including multiline values with `|`
- **Falls back to line parsing** for simple `key: value` format
- **Type coercion:** strings, numbers, booleans, objects, arrays
- **Quote stripping:** removes outer quotes from values
- **Robust:** returns empty dict if parsing fails, never throws

### Supported YAML Features
```yaml
---
name: some-skill
description: |
  This is a multiline
  description using the
  literal block scalar operator
enabled: true
timeout: 30
tags: ["a", "b", "c"]  # or tags: a,b,c
---
```

### Usage in OpenClaw

Used for:
- SKILL.md files (skill metadata)
- Hook configuration files
- Plugin manifests
- General markdown documents with metadata

---

## Compatibility Analysis

### Can GhostPost Context Files Accept YAML Frontmatter?

**YES — 100% Compatible**

Reason: OpenClaw's parser explicitly handles both:
1. Files starting with `---` (YAML frontmatter)
2. Files starting with `#` (no frontmatter)

If we add YAML frontmatter to GhostPost context files (lines 1-2 before the `#`):

```markdown
---
schema_version: "1"
type: "system_brief"
generated_at: "2026-02-25T13:56:00Z"
---

# System Brief
...
```

OpenClaw would:
1. Extract the frontmatter block
2. Parse it into dict: `{schema_version: "1", type: "system_brief", ...}`
3. Render the markdown body as-is
4. Never break on the HTML comment version

### Current GhostPost HTML Comment Version

OpenClaw's parser **ignores HTML comments** — they're just part of the markdown body:
- `<!-- schema_version: 1 -->` would appear as-is in the rendered body
- Adding YAML frontmatter **before** the header would not conflict
- The `#` header would still be the first markdown element

---

## Recommended Format (Proposed)

### Option A: Add YAML Frontmatter (Recommended)

**File:** `/home/athena/ghostpost/context/SYSTEM_BRIEF.md`

```markdown
---
schema_version: "1"
context_type: "system_brief"
generated_at: "2026-02-25T13:56:00Z"
retention: "24h"
---

# System Brief
_Generated: 2026-02-25 13:56 UTC_
...
```

**Advantages:**
- **Parseable:** OpenClaw can extract metadata without regex/parsing markdown
- **Extensible:** Add new fields (retention, generated_at, type) without format change
- **Consistent:** Matches identity files and research outputs
- **Machine-readable:** Tools can verify format version programmatically
- **Standards-compliant:** Jekyll/Hugo/static site generators recognize this format

**Action Required in Code:**
```python
# In src/engine/context_writer.py — replace all:
lines = [
    "# System Brief",
    "<!-- schema_version: 1 -->",
    f"_Generated: {now_str}_",
    ...
]

# With:
lines = [
    "---",
    'schema_version: "1"',
    'context_type: "system_brief"',
    f'generated_at: "{now_iso}"',
    "---",
    "",
    "# System Brief",
    f"_Generated: {now_str}_",
    ...
]
```

### Option B: Keep HTML Comments (Current Approach)

**Pros:**
- No code changes needed
- Already working

**Cons:**
- Not machine-parseable
- Inconsistent with identity files
- HTML comments are processed as markdown (visible in some renderers)
- No type/structure information

---

## Files That Need Updates

### If Migrating to YAML Frontmatter:

| File | Lines Changed | Reason |
|------|-------|------|
| `src/engine/context_writer.py` | Lines 195-198 (and 8 others) | Replace HTML comment with YAML block |
| `src/engine/notifications.py` | Lines 196, 239 | Same replacement |
| (Optional) `src/engine/context_writer.py` | Parse & validate | Add validation that schema_version is present |

**Scope:** 11 locations in 2 files

---

## Summary: Format Compatibility Matrix

```
Format Source → Can Parse?
─────────────────────────────
HTML Comments (current)      ✓ Visible in markdown, not machine-parsed
YAML Frontmatter (proposed)  ✓ Parseable by OpenClaw, Jekyll, Hugo, etc.
Line-based YAML (identities) ✓ Used in config/identities/*.md
SKILL.md frontmatter         ✓ Uses YAML, parsed by skills/frontmatter.ts
```

**Conclusion:** Adding YAML frontmatter to GhostPost context files is fully compatible with all existing parsers and consistent with project conventions.

