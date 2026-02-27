---
name: ghostpost_goals
description: Set target outcomes for email threads, evaluate completion via LLM against acceptance criteria, and track goal lifecycle to extraction.
user-invocable: true
metadata: {"openclaw": {"emoji": "🎯", "requires": {"bins": ["ghostpost"]}}}
---

# GhostPost Goals

Set target outcomes for email threads. Goals have acceptance criteria that the LLM evaluates against thread content. When met, knowledge is auto-extracted.

## When to invoke

- Setting a desired outcome for a conversation (meeting, agreement, delivery)
- Checking if a thread's goal has been achieved after new emails arrive
- Triage action says "check goal" for an in-progress goal
- Marking a goal as met or abandoned

## Entry point

```bash
ghostpost goal <id> --set "..." --criteria "..." --json
```

## Commands

```bash
ghostpost goal <id> --set "Get meeting scheduled" --criteria "Date and time confirmed" --json   # Set goal
ghostpost goal <id> --check --json                                                               # LLM evaluates emails against criteria
ghostpost goal <id> --status met --json                                                          # Mark as met (triggers extraction)
ghostpost goal <id> --status abandoned --json                                                    # Mark as abandoned
ghostpost goal <id> --clear --json                                                               # Remove goal entirely
```

## Goal lifecycle

1. Set goal with `--set` and `--criteria`
2. Work toward goal via replies (ghostpost-reply)
3. After new emails arrive, check with `--check`
4. LLM evaluates all thread emails against criteria
5. Mark `--status met` → auto-triggers knowledge extraction → surfaces in `COMPLETED_OUTCOMES.md`
6. Thread auto-transitions to GOAL_MET state

## Rules

- Write `--criteria` as something an LLM can evaluate against email content — be specific
- Statuses: in_progress (default), met (triggers extraction), abandoned
- Setting status to "met" → auto-triggers knowledge extraction → surfaces in `context/COMPLETED_OUTCOMES.md`
- Setting status to "met" → thread auto-transitions to GOAL_MET state
- Run `--check` after new emails arrive on any in_progress thread
- Active goals visible at: `context/ACTIVE_GOALS.md`
