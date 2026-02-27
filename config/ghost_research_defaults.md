---
default_language: "pt-PT"
default_email_tone: "direct-value"
default_aggressiveness: "standard"
default_auto_reply_mode: "draft-for-approval"
default_max_auto_replies: 3
default_max_email_length: 150
default_include_meeting_request: false
default_include_case_study: false
default_follow_up_days: 3
---

# Ghost Research Defaults

These are the default settings applied to all research campaigns unless overridden.

## Language
- Default: pt-PT (European Portuguese)
- Applies to email output only; research documents are always in English
- Override per-campaign or per-company in batch files

## Email Tone
- direct-value: Bold, ROI-focused, leads with numbers (DEFAULT for sales)
- consultative: Deep understanding, leads with insight
- relationship-first: Warm, personal, connection-focused
- challenger-sale: Provocative, challenges assumptions

## Auto-Reply Mode
- draft-for-approval: Agent drafts, human approves (DEFAULT)
- autonomous: Agent responds automatically
- notify-only: Agent alerts, takes no action

## Escalation Triggers
Keywords that always require human approval regardless of auto-reply mode:
- pricing, price, cost, budget
- contract, agreement, terms
- legal, lawyer, court
- payment, invoice, billing
- deadline, urgent, emergency
