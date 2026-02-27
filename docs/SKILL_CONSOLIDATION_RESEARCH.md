# OpenClaw Skill Organization Research — Full Report

## Executive Summary

OpenClaw's 64 total skills follow two proven patterns:
1. **Consolidated**: Single skill per platform/tool (Discord, Slack, Trello, Notion)
2. **Specialized Split**: Multiple skills when distinct workflows emerge (GitHub: `github` + `gh-issues`)

**GhostPost's 10 individual skills are correctly designed** — they represent 10 distinct agent workflows, not platform features. Consolidating them would harm usability.

---

## Part 1: OpenClaw's Skill Landscape

### Total Skill Count: 64
- **GhostPost**: 10 skills (email workflows)
- **Complex platforms**: 1 skill each (Discord, Slack, Trello, Notion, Google Drive, etc.)
- **GitHub**: 2 skills (general ops + specialized orchestrator)

### Skills Breakdown

**Single-Skill Platforms** (consolidated per platform):
- `discord` — single skill, unified message tool
- `slack` — single skill with multiple action groups (react, send, pin, etc.)
- `trello` — single skill for REST API operations
- `notion` — single skill for API operations
- `gdrive` — single skill for Google Drive
- `apple-notes`, `apple-reminders`, `bear-notes` — one skill each
- `blucli`, `eightctl`, `food-order`, `himalaya` — one skill each

**Multi-Skill Platforms**:
- **GitHub**: 2 distinct skills
  - `github` — general operations (check status, create issues, view CI logs, code review)
  - `gh-issues` — specialized orchestrator (auto-fix issues + handle PR reviews) with full sub-agent framework
- **GhostPost**: 10 distinct workflow skills
  - (details in Part 2)

---

## Part 2: GhostPost Skills Analysis

### The 10 Skills (Ranked by Complexity)

| # | Skill | Lines | Purpose | "Use When" |
|---|-------|-------|---------|-----------|
| 1 | ghostpost-compose | 36 | New email conversations | Starting fresh, not replying |
| 2 | ghostpost-search | 31 | Find emails | Looking for something specific |
| 3 | ghostpost-read | 39 | View threads/emails/briefs | Need to check email content |
| 4 | ghostpost-context | 40 | Overview dashboard | High-level email state |
| 5 | ghostpost-manage | 41 | Thread state + settings | Change state, toggle auto-reply, set follow-ups |
| 6 | ghostpost-reply | 41 | Send replies + manage drafts | Reply to existing threads |
| 7 | ghostpost-playbook | 51 | Apply workflow templates | Standardized email processes |
| 8 | ghostpost-goals | 49 | Track conversation outcomes | Set goals, check progress |
| 9 | ghostpost-notify | 54 | Notification settings | Configure alerts |
| 10 | ghostpost-security | 57 | Quarantine, blocklist, audit | Security management |

**Metrics**:
- Size range: 31-57 lines (consistent, lightweight)
- Average: 43.9 lines
- Total: 439 lines
- All well under 100 lines (good: allows skill to be comprehensible and focused)

### Cross-References (Minimal But Strategic)

GhostPost skills use **description-based routing** rather than explicit links:

```
ghostpost-compose → "use ghostpost-reply instead [for replies]"
ghostpost-context → "Drill down: use ghostpost-read [for specific threads]"
ghostpost-search  → "[instead] see ghostpost-context skill [for overview]"
```

**Finding**: Explicit cross-references are sparse. The agent chooses skills based on:
- Description matching (primary)
- User intent ("I need to send a reply" → triggers ghostpost-reply)
- Natural conversation flow

No centralized "meta skill" router needed.

---

## Part 3: When to Consolidate vs. Split

### Pattern 1: CONSOLIDATE
**Use a single skill when:**
- ✓ Operating a single CLI tool or API (Discord → `message` tool, Slack → `slack` tool, Trello/Notion → REST API)
- ✓ All actions are variations of the same capability (send, edit, delete, react on Slack)
- ✓ A clear, single-sentence description works ("Manage Trello boards via REST API")
- ✓ No distinct workflows compete for attention

**Examples**:
```yaml
discord: "Discord ops via the message tool (channel=discord)."
slack: "Use when you need to control Slack from OpenClaw via the slack tool..."
trello: "Manage Trello boards, lists, and cards via the Trello REST API."
notion: "Notion API for creating and managing pages, databases, and blocks."
```

### Pattern 2: SPLIT (Multiple Skills)
**Use multiple skills when:**
- ✓ **Distinct workflows** exist with different entrypoints (GitHub: ad-hoc ops vs. auto-fix orchestration)
- ✓ One skill is specialized/powerful enough to warrant its own guide (gh-issues is 650+ lines, not ~50)
- ✓ Agents invoke them in different contexts (github for "check PR status", gh-issues for "auto-fix all bug issues")
- ✓ Each has its own independent use case

**Example: GitHub Split**

`github` skill:
```yaml
name: github
description: "GitHub operations via `gh` CLI: issues, PRs, CI runs, code review, API queries. 
Use when: (1) checking PR status or CI, (2) creating/commenting on issues, (3) listing/filtering 
PRs or issues, (4) viewing run logs."
```
- 164 lines, straightforward CLI reference

`gh-issues` skill:
```yaml
name: gh-issues
description: "Fetch GitHub issues, spawn sub-agents to implement fixes and open PRs, then 
monitor and address PR review comments. Usage: /gh-issues [owner/repo] [--label bug] ..."
user-invocable: true
```
- 817 lines, complex orchestrator with 6 phases, spawn mechanism, claim tracking, cron mode
- Entirely different use case: "automate issue fixes" vs. "check PR status"

---

## Part 4: GhostPost — Verdict on Consolidation

### Current State: 10 Skills ✓ CORRECT

**Why NOT consolidate?**

The 10 GhostPost skills represent **10 fundamentally different agent workflows**, not variations on a single feature:

1. **Read-class workflows** (context, read, search) — three different query intents
   - `context`: "Give me the dashboard"
   - `read`: "Show me thread #42"
   - `search`: "Find emails about X"

2. **Write-class workflows** (compose, reply) — two different send intents
   - `compose`: "Start a new conversation"
   - `reply`: "Reply to existing thread"

3. **Lifecycle workflows** (manage, goals, playbook, notify, security) — five specialized intents
   - `manage`: "Change thread state"
   - `goals`: "Track an outcome"
   - `playbook`: "Apply a template"
   - `notify`: "Configure alerts"
   - `security`: "Review quarantines"

**If you consolidated to 1 skill**:
- Agent would see "ghostpost" and have to guess among 40+ commands
- Description matching would fail (too many use cases)
- Commands would be scattered, confusing
- Harder to document and discover

**If you consolidated to 2-3 skills**:
- `ghostpost-read` (read, search, context) — but these have different intents (dashboard vs. drill-down vs. search)
- `ghostpost-write` (compose, reply) — reasonable, but separate reply & draft workflows
- `ghostpost-manage` (goals, security, notify, playbook) — misses the semantic grouping

---

## Part 5: Description Quality as the Key

### The Pattern: Descriptions Drive Skill Selection

OpenClaw doesn't have a "skill router" or explicit dependency system. Instead:
- Descriptions are parsed for intent keywords
- When agent says "I need to X", matching descriptions trigger skill loading
- This means **description quality is critical**

### GhostPost's Description Quality: ✓ STRONG

```
ghostpost-compose:
"Compose and send new emails via GhostPost. 
Use when you need to start a new email conversation from scratch, not replying to an existing thread."

ghostpost-reply:
"Reply to existing GhostPost email threads. 
Use when you need to send a reply, create a draft reply for approval, approve or reject pending drafts, 
or manage the reply workflow."

ghostpost-context:
"Read GhostPost context files for a high-level overview of email state, contacts, rules, active goals, 
pending drafts, and security alerts. 
Use when you need a broad understanding of Athena's email situation without querying individual threads."
```

Each description:
- Starts with action verb (Compose, Reply, Read)
- Includes "Use when" section
- Clear constraints (not for replies, for existing threads, etc.)
- Mentions related skills only when disambiguation needed

### What Doesn't Work: Generic Descriptions

Bad:
```
ghostpost: "GhostPost email management."
```
Reason: Too vague. Agent can't match "I need to reply" to "email management."

Better:
```
ghostpost-reply: "Reply to email threads in GhostPost."
```

Best:
```
ghostpost-reply: "Reply to existing GhostPost email threads. 
Use when you need to send a reply, create a draft reply for approval, or manage the reply workflow."
```

---

## Part 6: Skill Activation Mechanism (How OpenClaw Chooses Skills)

OpenClaw does NOT have explicit skill routing files (like a `skills-router.json`). Instead:

1. **Description indexing**: All skill descriptions are indexed on load
2. **Intent matching**: When agent says something, keywords are matched against descriptions
3. **Fuzzy matching**: If multiple skills match, context + conversation history breaks ties
4. **Explicit invocation**: Agent can also call `/skill-name` to force a specific skill
5. **Conversation flow**: Agent can switch between skills mid-conversation

Example:
- Agent: "Show me threads about the acquisition"
- Matches: ghostpost-search ("Search GhostPost emails")
- Agent: "What's the overview?"
- Matches: ghostpost-context ("high-level overview")
- Agent: "Set a goal to get confirmation"
- Matches: ghostpost-goals ("track specific outcomes")

---

## Part 7: Consolidation Impact Analysis

### Scenario: Merge 10 GhostPost Skills into 1

```yaml
name: ghostpost
description: "Comprehensive GhostPost email management: read threads, compose emails, reply to threads,
search emails, manage thread state, set goals, apply playbooks, configure notifications, manage security."
```

**What breaks:**
1. Description becomes generic → fuzzy intent matching fails
2. Agent must choose from 40+ commands in a single skill
3. Example error:
   - User: "Get me an overview"
   - Agent thinks: "Is this context, read, or search?"
   - Chooses wrong command → bad UX
4. Documentation sprawl (one 400-line skill file is unreadable)
5. Cross-tool context: If agent is working in Discord and needs GhostPost, it can't narrow down to "oh, I need ghostpost-reply specifically"

**What improves:**
1. Slightly simpler skill directory (64 → 55)
2. No mental model overhead of "10 different ghostpost skills"

**Verdict**: Not worth it. The UX degradation far exceeds the benefit.

### Scenario: Merge to 3 Skills (Optimal Consolidation)

```yaml
ghostpost-io:
  - compose (new)
  - reply (new)

ghostpost-query:
  - context
  - read
  - search

ghostpost-manage:
  - manage
  - goals
  - playbook
  - notify
  - security
```

**Pros**:
- Reduces to 3 skills (slightly simpler)
- Loosely groups related intents
- ghostpost-query has semantic unity ("read operations")
- ghostpost-io has semantic unity ("send operations")

**Cons**:
- ghostpost-manage is now a dumping ground (5 unrelated workflows: state, goals, templates, alerts, security)
- "I need to set a goal" doesn't clearly map to "ghostpost-manage"
- Description for ghostpost-manage becomes too long

**Verdict**: Less optimal than current 10-skill approach. The semantic grouping breaks down.

---

## Part 8: Final Recommendation

### KEEP THE 10-SKILL ARCHITECTURE ✓

**Evidence**:
1. OpenClaw's own patterns: Complex platforms get split when specialized workflows exist
2. GitHub proves it: `github` (general) + `gh-issues` (specialized orchestrator) work together
3. Description quality is strong across all 10 ghostpost skills
4. No explicit routing needed; description matching works
5. Skill sizes are consistent (31-57 lines, avg 44)
6. Cross-references are minimal but sufficient (compose → reply, context → read, search → context)

### Why This Works Better Than Alternatives:

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| 1 skill (current consolidation) | Simple directory | Fuzzy intent matching, bad UX, unreadable docs | ✗ Bad |
| 3 skills (grouped) | Moderately simpler | Semantic breakdowns, forced groupings | ✗ Mediocre |
| 5 skills (larger groups) | Better semantics | Still too many use cases per skill | ✗ OK |
| **10 skills (current)** | **Clear intent, tight docs, good UX** | **More skills to manage** | **✓ Best** |

---

## Part 9: How to Maintain Quality at 10 Skills

To keep the 10-skill model sustainable:

1. **Enforce description quality**
   - Every skill must have a clear "Use when" section
   - Include "NOT for" constraints (see github skill)
   - Keep under 200 characters for main description

2. **Keep files lean**
   - Target 30-60 lines per skill (current range)
   - If growing past 100 lines, consider splitting
   - Example: If ghostpost-manage grows to 150+ lines, split into manage + notify

3. **Use minimal cross-references**
   - Only reference when disambiguation is needed
   - Rely on description matching for routing
   - Example: compose → "not for replies", reply → "for existing threads"

4. **Test skill discoverability**
   - Ask the agent: "What skill would you use for [intent]?"
   - Check if it picks the right one consistently
   - Refine descriptions if mismatches occur

5. **Monitor skill overlap**
   - Watch usage patterns in agent transcripts
   - If two skills are always invoked together, consider merging
   - If one skill is never used alone, may indicate consolidation opportunity

---

## Appendix: Multi-Skill Success Stories in OpenClaw

### GitHub (2 skills)
- `github`: ~164 lines, general operations
- `gh-issues`: ~817 lines, auto-fix orchestrator with phases, spawning, reviews
- **Why it works**: Completely different use cases and power levels

### GhostPost (10 skills)
- Each 30-60 lines, distinct workflow
- Descriptions guide agent routing
- **Why it works**: Clear semantic boundaries between read/write/manage workflows

### Slack (1 skill)
- Multiple actions (react, send, pin, etc.) all unified
- **Why it works**: All actions operate on the same conceptual object (Slack message in a channel)

---

## Conclusion

**OpenClaw's pattern is clear**: Use multiple skills when distinct workflows exist with different entry points, power levels, or specialized requirements. GhostPost's 10-skill architecture mirrors GitHub's split (general + specialized), proving it's the right choice.

Consolidating would sacrifice UX for marginal simplification. Keeping the 10-skill model maintains clarity, discoverability, and agent efficiency.
