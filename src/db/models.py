"""GhostPost database models — SQLAlchemy 2.0 declarative style."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_thread_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    subject: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String, default="NEW")
    priority: Mapped[str | None] = mapped_column(String)
    auto_reply_mode: Mapped[str] = mapped_column(String, default="off")
    follow_up_days: Mapped[int] = mapped_column(Integer, default=3)
    next_follow_up_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    playbook: Mapped[str | None] = mapped_column(String)
    goal: Mapped[str | None] = mapped_column(Text)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text)
    goal_status: Mapped[str | None] = mapped_column(String)  # in_progress, met, abandoned
    notes: Mapped[str | None] = mapped_column(Text)
    security_score_avg: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    research_campaign_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="SET NULL"), nullable=True
    )

    emails: Mapped[list["Email"]] = relationship(
        back_populates="thread", lazy="selectin", cascade="all, delete-orphan"
    )
    drafts: Mapped[list["Draft"]] = relationship(
        back_populates="thread", lazy="noload", cascade="all, delete-orphan"
    )


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        Index("ix_emails_date", "date"),
        Index("ix_emails_thread_id", "thread_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    gmail_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    message_id: Mapped[str | None] = mapped_column(String)
    from_address: Mapped[str | None] = mapped_column(String)
    to_addresses: Mapped[dict | None] = mapped_column(JSONB)
    cc: Mapped[dict | None] = mapped_column(JSONB)
    bcc: Mapped[dict | None] = mapped_column(JSONB)
    subject: Mapped[str | None] = mapped_column(Text)
    body_plain: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    headers: Mapped[dict | None] = mapped_column(JSONB)
    attachment_metadata: Mapped[dict | None] = mapped_column(JSONB)
    security_score: Mapped[int | None] = mapped_column(Integer)
    sentiment: Mapped[str | None] = mapped_column(String)
    urgency: Mapped[str | None] = mapped_column(String)
    action_required: Mapped[dict | None] = mapped_column(JSONB)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    thread: Mapped["Thread"] = relationship(back_populates="emails")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="email", lazy="selectin", cascade="all, delete-orphan"
    )


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String)
    aliases: Mapped[dict | None] = mapped_column(JSONB)
    relationship_type: Mapped[str] = mapped_column(String, default="unknown")
    communication_frequency: Mapped[str | None] = mapped_column(String)
    avg_response_time: Mapped[str | None] = mapped_column(String)
    preferred_style: Mapped[str | None] = mapped_column(String)
    topics: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    enrichment_source: Mapped[str | None] = mapped_column(String)
    last_interaction: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"))
    filename: Mapped[str | None] = mapped_column(String)
    content_type: Mapped[str | None] = mapped_column(String)
    size: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str | None] = mapped_column(String)
    gmail_attachment_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    email: Mapped["Email"] = relationship(back_populates="attachments")


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))

    thread: Mapped["Thread | None"] = relationship(back_populates="drafts")
    gmail_draft_id: Mapped[str | None] = mapped_column(String)
    to_addresses: Mapped[dict | None] = mapped_column(JSONB)
    cc: Mapped[dict | None] = mapped_column(JSONB)
    bcc: Mapped[dict | None] = mapped_column(JSONB)
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, approved, rejected, sent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_timestamp", "timestamp"),
        Index("ix_audit_log_action_type", "action_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    action_type: Mapped[str] = mapped_column(String, index=True)  # reply_sent, draft_created, state_changed, goal_set, etc.
    thread_id: Mapped[int | None] = mapped_column(Integer)
    email_id: Mapped[int | None] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String, default="system")  # user, agent, system
    details: Mapped[dict | None] = mapped_column(JSONB)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_timestamp", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    email_id: Mapped[int | None] = mapped_column(Integer)
    thread_id: Mapped[int | None] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String)  # injection_detected, anomaly, rate_limit_exceeded, etc.
    severity: Mapped[str] = mapped_column(String)  # critical, high, medium, low
    details: Mapped[dict | None] = mapped_column(JSONB)
    resolution: Mapped[str | None] = mapped_column(String)  # pending, approved, dismissed
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    cc: Mapped[dict | None] = mapped_column(JSONB)
    bcc: Mapped[dict | None] = mapped_column(JSONB)
    actor: Mapped[str] = mapped_column(String, default="user")
    total_recipients: Mapped[int] = mapped_column(Integer)
    total_clusters: Mapped[int] = mapped_column(Integer)
    clusters_sent: Mapped[int] = mapped_column(Integer, default=0)
    clusters_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, in_progress, completed, failed, cancelled
    error_log: Mapped[dict | None] = mapped_column(JSONB)
    next_send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["BatchItem"]] = relationship(
        back_populates="batch_job", lazy="selectin", cascade="all, delete-orphan"
    )


class BatchItem(Base):
    __tablename__ = "batch_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_job_id: Mapped[int] = mapped_column(ForeignKey("batch_jobs.id", ondelete="CASCADE"))
    cluster_index: Mapped[int] = mapped_column(Integer)
    recipients: Mapped[dict] = mapped_column(JSONB)  # list of email addresses
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, sent, failed
    gmail_ids: Mapped[dict | None] = mapped_column(JSONB)  # list of gmail message IDs
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch_job: Mapped["BatchJob"] = relationship(back_populates="items")


class ThreadOutcome(Base):
    __tablename__ = "thread_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), unique=True, index=True)
    outcome_type: Mapped[str] = mapped_column(String)  # agreement, decision, delivery, meeting, other
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)  # structured: contacts involved, dates, amounts, next steps
    outcome_file: Mapped[str | None] = mapped_column(String)  # path to markdown file in memory/outcomes/
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchBatch(Base):
    __tablename__ = "research_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    total_companies: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, in_progress, paused, completed, cancelled
    defaults: Mapped[dict | None] = mapped_column(JSONB)  # batch-level defaults (identity, goal, language, etc.)
    source_file: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaigns: Mapped[list["ResearchCampaign"]] = relationship(
        back_populates="batch", lazy="selectin", cascade="all, delete-orphan"
    )


class ResearchCampaign(Base):
    __tablename__ = "research_campaigns"
    __table_args__ = (
        Index("ix_research_campaigns_status", "status"),
        Index("ix_research_campaigns_batch_id", "batch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String)
    company_slug: Mapped[str] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    industry: Mapped[str | None] = mapped_column(String)
    identity: Mapped[str] = mapped_column(String, default="default")
    goal: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String, default="pt-PT")
    contact_name: Mapped[str | None] = mapped_column(String)
    contact_email: Mapped[str | None] = mapped_column(String)
    contact_role: Mapped[str | None] = mapped_column(String)
    cc: Mapped[str | None] = mapped_column(String)  # comma-separated CC emails
    extra_context: Mapped[str | None] = mapped_column(Text)  # free-text extra context for pipeline
    email_tone: Mapped[str] = mapped_column(String, default="direct-value")
    auto_reply_mode: Mapped[str] = mapped_column(String, default="draft-for-approval")
    max_auto_replies: Mapped[int] = mapped_column(Integer, default=3)

    # Pipeline state
    status: Mapped[str] = mapped_column(String, default="queued")  # queued, phase_1..phase_8, sending, sent, draft_pending, failed, skipped
    phase: Mapped[int] = mapped_column(Integer, default=0)  # 0-8
    error: Mapped[str | None] = mapped_column(Text)

    # Research data (accumulated through phases)
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    research_data: Mapped[dict | None] = mapped_column(JSONB)  # {dossier, opportunities, peer_intel, value_plan}

    # Email output
    email_subject: Mapped[str | None] = mapped_column(Text)
    email_body: Mapped[str | None] = mapped_column(Text)
    output_dir: Mapped[str | None] = mapped_column(String)

    # Linking
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("research_batches.id", ondelete="SET NULL"))
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("threads.id", ondelete="SET NULL"))
    queue_position: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped["ResearchBatch | None"] = relationship(back_populates="campaigns")
    thread: Mapped["Thread | None"] = relationship(foreign_keys=[thread_id])
