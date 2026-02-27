"""Batch email queue — splits large recipient lists into clusters of 20, sent 1 hour apart."""

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.api.events import publish_event
from src.db.models import BatchItem, BatchJob
from src.db.session import async_session
from src.gmail.scheduler import scheduler
from src.gmail.send import send_new
from src.security.audit import log_action
from src.security.safeguards import get_blocklist, increment_rate

logger = logging.getLogger("ghostpost.engine.batch")

CLUSTER_SIZE = 20


def _split_into_clusters(recipients: list[str]) -> list[list[str]]:
    """Split a list of recipients into clusters of CLUSTER_SIZE."""
    return [
        recipients[i : i + CLUSTER_SIZE]
        for i in range(0, len(recipients), CLUSTER_SIZE)
    ]


async def create_batch_job(
    to_list: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    actor: str = "user",
) -> BatchJob:
    """Create a batch job, send the first cluster immediately, schedule the rest."""
    # Pre-validate all recipients against blocklist
    blocklist = await get_blocklist()
    blocked = [addr for addr in to_list if addr.lower() in [b.lower() for b in blocklist]]
    if blocked:
        raise ValueError(f"Blocked recipients: {', '.join(blocked)}")

    clusters = _split_into_clusters(to_list)
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        job = BatchJob(
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            actor=actor,
            total_recipients=len(to_list),
            total_clusters=len(clusters),
            status="in_progress",
            next_send_at=now + timedelta(hours=1) if len(clusters) > 1 else None,
        )
        session.add(job)
        await session.flush()

        for idx, cluster in enumerate(clusters):
            item = BatchItem(
                batch_job_id=job.id,
                cluster_index=idx,
                recipients=cluster,
                status="pending",
            )
            session.add(item)

        await session.commit()
        await session.refresh(job)
        job_id = job.id

    await log_action(
        action_type="batch_created",
        actor=actor,
        details={
            "batch_job_id": job_id,
            "total_recipients": len(to_list),
            "total_clusters": len(clusters),
            "subject": subject,
        },
    )

    # Send the first cluster immediately
    await process_next_cluster(job_id)

    # Schedule remaining clusters 1 hour apart
    for i in range(1, len(clusters)):
        run_time = now + timedelta(hours=i)
        scheduler.add_job(
            process_next_cluster,
            "date",
            run_date=run_time,
            args=[job_id],
            id=f"batch_{job_id}_cluster_{i}",
            replace_existing=True,
        )

    # Reload to return current state
    async with async_session() as session:
        job = await session.get(BatchJob, job_id)
    return job


async def process_next_cluster(batch_job_id: int) -> None:
    """Send the next pending cluster for a batch job."""
    async with async_session() as session:
        job = await session.get(BatchJob, batch_job_id)
        if not job or job.status not in ("pending", "in_progress"):
            logger.info(f"Batch {batch_job_id} skipped (status={job.status if job else 'not found'})")
            return

        # Find next pending item
        result = await session.execute(
            select(BatchItem)
            .where(BatchItem.batch_job_id == batch_job_id, BatchItem.status == "pending")
            .order_by(BatchItem.cluster_index)
            .limit(1)
        )
        item = result.scalar_one_or_none()
        if not item:
            logger.info(f"Batch {batch_job_id}: no pending clusters")
            return

        item_id = item.id
        recipients = item.recipients
        cluster_index = item.cluster_index

    # Send each recipient individually
    gmail_ids = []
    errors = []
    for addr in recipients:
        try:
            result = await send_new(
                to=addr,
                subject=job.subject,
                body=job.body,
                cc=job.cc,
                bcc=job.bcc,
                actor=job.actor,
            )
            gmail_ids.append(result.get("id"))
            await increment_rate(job.actor)
        except Exception as e:
            logger.error(f"Batch {batch_job_id} cluster {cluster_index}: failed to send to {addr}: {e}")
            errors.append({"recipient": addr, "error": str(e)})

    # Update item
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        item = await session.get(BatchItem, item_id)
        item.gmail_ids = gmail_ids
        item.sent_at = now

        if errors and len(errors) == len(recipients):
            item.status = "failed"
            item.error = "; ".join(e["error"] for e in errors)
        else:
            item.status = "sent"
            if errors:
                item.error = "; ".join(f"{e['recipient']}: {e['error']}" for e in errors)

        # Update job counters
        job = await session.get(BatchJob, batch_job_id)
        if item.status == "sent":
            job.clusters_sent += 1
        else:
            job.clusters_failed += 1

        # Check if all clusters are done
        pending_count = (await session.execute(
            select(BatchItem)
            .where(BatchItem.batch_job_id == batch_job_id, BatchItem.status == "pending")
        )).scalars().all()

        if not pending_count:
            job.status = "completed" if job.clusters_failed == 0 else "failed"
            job.next_send_at = None
        else:
            job.next_send_at = now + timedelta(hours=1)

        job.updated_at = now

        if errors:
            existing_errors = job.error_log or []
            existing_errors.extend(errors)
            job.error_log = existing_errors

        await session.commit()

    await publish_event("batch_cluster_sent", {
        "batch_job_id": batch_job_id,
        "cluster_index": cluster_index,
        "status": item.status,
        "sent_count": len(gmail_ids),
        "error_count": len(errors),
    })

    logger.info(f"Batch {batch_job_id} cluster {cluster_index}: {len(gmail_ids)} sent, {len(errors)} failed")


async def cancel_batch(batch_job_id: int, actor: str = "user") -> BatchJob:
    """Cancel a pending/in_progress batch job. Removes scheduled APScheduler jobs."""
    async with async_session() as session:
        job = await session.get(BatchJob, batch_job_id)
        if not job:
            raise ValueError(f"Batch job {batch_job_id} not found")
        if job.status not in ("pending", "in_progress"):
            raise ValueError(f"Batch job {batch_job_id} is {job.status}, cannot cancel")

        job.status = "cancelled"
        job.next_send_at = None
        job.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(job)

    # Remove scheduled APScheduler jobs
    for i in range(job.total_clusters):
        job_id = f"batch_{batch_job_id}_cluster_{i}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass  # Job may not exist (already ran or wasn't scheduled)

    await log_action(
        action_type="batch_cancelled",
        actor=actor,
        details={"batch_job_id": batch_job_id},
    )

    return job


async def resume_pending_batches() -> int:
    """Resume in-progress batch jobs after restart. Returns count of resumed jobs."""
    async with async_session() as session:
        result = await session.execute(
            select(BatchJob).where(BatchJob.status == "in_progress")
        )
        jobs = result.scalars().all()

    resumed = 0
    now = datetime.now(timezone.utc)
    for job in jobs:
        # Schedule next cluster — use next_send_at if in the future, otherwise send soon
        run_time = job.next_send_at if job.next_send_at and job.next_send_at > now else now + timedelta(seconds=30)
        scheduler.add_job(
            process_next_cluster,
            "date",
            run_date=run_time,
            args=[job.id],
            id=f"batch_{job.id}_resume",
            replace_existing=True,
        )
        resumed += 1
        logger.info(f"Resumed batch job {job.id}, next cluster at {run_time}")

    if resumed:
        logger.info(f"Resumed {resumed} pending batch jobs")
    return resumed
