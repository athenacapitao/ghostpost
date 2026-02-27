"""Pydantic v2 response models."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# --- Pagination ---

class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


# --- Contacts ---

class ContactOut(BaseModel):
    id: int
    email: str
    name: str | None
    relationship_type: str
    communication_frequency: str | None
    preferred_style: str | None
    topics: list | dict | None
    last_interaction: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactListResponse(PaginatedResponse):
    items: list[ContactOut]


# --- Attachments ---

class AttachmentOut(BaseModel):
    id: int
    filename: str | None
    content_type: str | None
    size: int | None
    gmail_attachment_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Emails ---

class EmailOut(BaseModel):
    id: int
    gmail_id: str
    thread_id: int
    message_id: str | None
    from_address: str | None
    to_addresses: list | None
    cc: list | None
    subject: str | None
    body_plain: str | None
    body_html: str | None
    date: datetime | None
    security_score: int | None = None
    sentiment: str | None = None
    urgency: str | None = None
    action_required: dict | None = None
    is_read: bool
    is_sent: bool
    is_draft: bool
    attachments: list[AttachmentOut]
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailListResponse(PaginatedResponse):
    items: list[EmailOut]


# --- Threads ---

class ThreadSummaryOut(BaseModel):
    id: int
    gmail_thread_id: str
    subject: str | None
    category: str | None
    state: str
    priority: str | None
    summary: str | None
    security_score_avg: int | None = None
    email_count: int = 0
    last_activity_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ThreadDetailOut(BaseModel):
    id: int
    gmail_thread_id: str
    subject: str | None
    category: str | None
    summary: str | None
    state: str
    priority: str | None
    auto_reply_mode: str
    follow_up_days: int
    next_follow_up_date: datetime | None
    playbook: str | None
    goal: str | None
    acceptance_criteria: str | None
    goal_status: str | None
    notes: str | None
    security_score_avg: int | None
    last_activity_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    emails: list[EmailOut]

    model_config = {"from_attributes": True}


class ThreadListResponse(PaginatedResponse):
    items: list[ThreadSummaryOut]


# --- Sync ---

class SyncStatusOut(BaseModel):
    running: bool
    last_sync: str | None
    last_history_id: str | None
    emails_synced: int
    threads_synced: int
    contacts_synced: int
    error: str | None


class SyncTriggerResponse(BaseModel):
    message: str


# --- Stats ---

class StatsOut(BaseModel):
    total_threads: int
    active_threads: int
    archived_threads: int
    total_emails: int
    total_contacts: int
    total_attachments: int
    unread_emails: int
    db_size_mb: float


# --- Phase 3+4 Schemas ---

class ReplyRequest(BaseModel):
    body: str
    cc: list[str] | None = None
    bcc: list[str] | None = None


class ComposeRequest(BaseModel):
    to: str | list[str]
    subject: str
    body: str
    cc: list[str] | None = None
    bcc: list[str] | None = None

    # Agent context — optional metadata for new thread
    goal: str | None = None
    acceptance_criteria: str | None = None
    playbook: str | None = None
    auto_reply_mode: str | None = None
    follow_up_days: int | None = None
    priority: str | None = None
    category: str | None = None
    notes: str | None = None

    @field_validator("to")
    @classmethod
    def validate_to(cls, v):
        addrs = [v] if isinstance(v, str) else v
        if not addrs or any(not a or not a.strip() for a in addrs):
            raise ValueError("Recipient address(es) cannot be empty")
        return v

    @field_validator("auto_reply_mode")
    @classmethod
    def validate_auto_reply_mode(cls, v):
        if v is not None and v not in ("off", "draft", "auto"):
            raise ValueError("auto_reply_mode must be 'off', 'draft', or 'auto'")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v is not None and v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be 'low', 'medium', 'high', or 'critical'")
        return v


class DraftRequest(BaseModel):
    to: str | list[str]
    subject: str
    body: str
    cc: list[str] | None = None
    bcc: list[str] | None = None

    @field_validator("to")
    @classmethod
    def validate_to(cls, v):
        addrs = [v] if isinstance(v, str) else v
        if not addrs or any(not a or not a.strip() for a in addrs):
            raise ValueError("Recipient address(es) cannot be empty")
        return v


class StateRequest(BaseModel):
    state: str
    reason: str | None = None


class FollowUpRequest(BaseModel):
    days: int


class AutoReplyRequest(BaseModel):
    mode: str  # off, draft, auto


class NotesRequest(BaseModel):
    notes: str


class GoalRequest(BaseModel):
    goal: str
    acceptance_criteria: str | None = None


class GoalStatusRequest(BaseModel):
    status: str  # in_progress, met, abandoned


class BlocklistRequest(BaseModel):
    email: str


class DraftOut(BaseModel):
    id: int
    thread_id: int | None
    to_addresses: list | None
    cc: list | None
    bcc: list | None
    subject: str | None
    body: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    action_type: str
    thread_id: int | None
    email_id: int | None
    actor: str
    details: dict | None

    model_config = {"from_attributes": True}


class SecurityEventOut(BaseModel):
    id: int
    timestamp: datetime
    email_id: int | None
    thread_id: int | None
    event_type: str
    severity: str
    details: dict | None
    resolution: str | None
    quarantined: bool

    model_config = {"from_attributes": True}


# --- Outcomes ---

# --- Batch ---

class BatchItemOut(BaseModel):
    id: int
    cluster_index: int
    recipients: list
    status: str
    gmail_ids: list | None
    error: str | None
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class BatchJobOut(BaseModel):
    id: int
    subject: str
    total_recipients: int
    total_clusters: int
    clusters_sent: int
    clusters_failed: int
    status: str
    next_send_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchJobDetailOut(BatchJobOut):
    items: list[BatchItemOut]


class ThreadOutcomeOut(BaseModel):
    id: int
    thread_id: int
    outcome_type: str
    summary: str
    details: dict | None
    outcome_file: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Ghost Research ---

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_SLUG_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class ResearchRequest(BaseModel):
    company_name: str
    goal: str
    identity: str = "default"
    language: str = "pt-PT"
    country: str | None = None
    industry: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_role: str | None = None
    cc: str | None = None  # comma-separated CC emails
    extra_context: str | None = Field(None, max_length=10000)
    email_tone: str = "direct-value"
    auto_reply_mode: str = "draft-for-approval"
    max_auto_replies: int = 3

    @field_validator("identity")
    @classmethod
    def validate_identity(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("identity must contain only alphanumeric chars, hyphens, and underscores")
        return v

    @field_validator("cc")
    @classmethod
    def validate_cc(cls, v: str | None) -> str | None:
        if not v:
            return v
        for email in v.split(","):
            email = email.strip()
            if email and not _EMAIL_RE.match(email):
                raise ValueError(f"Invalid CC email: {email}")
        return v


class ResearchBatchRequest(BaseModel):
    name: str
    companies: list[dict]
    defaults: dict | None = None


class ResearchCampaignOut(BaseModel):
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
    research_data: dict | None = None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ResearchBatchOut(BaseModel):
    id: int
    name: str
    total_companies: int
    completed: int
    failed: int
    skipped: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchBatchDetailOut(ResearchBatchOut):
    campaigns: list[ResearchCampaignOut]


# --- Identity CRUD ---

class IdentityRequest(BaseModel):
    identity_id: str
    company_name: str
    sender_name: str
    sender_title: str
    sender_email: str
    website: str | None = None
    industry: str | None = None
    tagline: str | None = None
    sender_phone: str | None = None
    sender_linkedin: str | None = None
    calendar_link: str | None = None
    body: str = Field("", max_length=50000)

    @field_validator("identity_id")
    @classmethod
    def validate_identity_id(cls, v: str) -> str:
        if not _SLUG_RE.match(v) or len(v) > 100:
            raise ValueError("identity_id must be 1-100 chars: alphanumeric, hyphens, underscores only")
        return v

    @field_validator("sender_email")
    @classmethod
    def validate_sender_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError(f"Invalid sender email: {v}")
        return v


class BatchImportCompany(BaseModel):
    company_name: str = Field(..., max_length=200)
    goal: str | None = Field(None, max_length=500)
    contact_name: str | None = Field(None, max_length=200)
    contact_email: str | None = Field(None, max_length=254)
    contact_role: str | None = Field(None, max_length=200)
    industry: str | None = Field(None, max_length=200)
    country: str | None = Field(None, max_length=100)
    cc: str | None = Field(None, max_length=1000)
    extra_context: str | None = Field(None, max_length=10000)


class BatchImportPreview(BaseModel):
    companies: list[BatchImportCompany]
    warnings: list[str]
    errors: list[str]
    column_mapping: dict[str, str]
    total: int


class IdentityOut(BaseModel):
    identity_id: str
    company_name: str
    sender_name: str
    sender_title: str
    sender_email: str
    website: str | None = None
    industry: str | None = None
    tagline: str | None = None
    sender_phone: str | None = None
    sender_linkedin: str | None = None
    calendar_link: str | None = None
    body: str = ""
