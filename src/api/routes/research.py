"""Ghost Research API endpoints."""

import json
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select

from src.api.dependencies import get_current_user
from src.api.schemas import (
    BatchImportPreview,
    IdentityOut,
    IdentityRequest,
    ResearchBatchOut,
    ResearchBatchRequest,
    ResearchCampaignOut,
    ResearchRequest,
)
from src.research.batch_import import parse_csv
from src.db.models import ResearchBatch, ResearchCampaign
from src.db.session import async_session
from src.research.identities import list_identities, load_identity, save_identity
from src.research.pipeline import create_campaign, request_cancel, run_pipeline
from src.research.queue import (
    cancel_batch,
    create_batch,
    get_batch_status,
    pause_batch,
    resume_batch,
    retry_campaign,
    run_batch,
    skip_campaign,
)

logger = logging.getLogger("ghostpost.api.research")

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/", status_code=201)
async def start_research(
    req: ResearchRequest,
    background_tasks: BackgroundTasks,
    user: str = Depends(get_current_user),
):
    """Start a single company research campaign."""
    campaign_id = await create_campaign(
        company_name=req.company_name,
        goal=req.goal,
        identity=req.identity,
        language=req.language,
        country=req.country,
        industry=req.industry,
        contact_name=req.contact_name,
        contact_email=req.contact_email,
        contact_role=req.contact_role,
        cc=req.cc,
        extra_context=req.extra_context,
        email_tone=req.email_tone,
        auto_reply_mode=req.auto_reply_mode,
        max_auto_replies=req.max_auto_replies,
    )

    # Run pipeline in background
    background_tasks.add_task(run_pipeline, campaign_id)

    return {"campaign_id": campaign_id, "status": "started"}


@router.post("/batch", status_code=201)
async def start_batch(
    req: ResearchBatchRequest,
    background_tasks: BackgroundTasks,
    user: str = Depends(get_current_user),
):
    """Start a batch research campaign with multiple companies."""
    if not req.companies:
        raise HTTPException(status_code=400, detail="No companies provided")

    batch_id = await create_batch(
        name=req.name,
        companies=req.companies,
        defaults=req.defaults,
    )

    # Run batch in background
    background_tasks.add_task(run_batch, batch_id)

    return {"batch_id": batch_id, "status": "started", "total_companies": len(req.companies)}


@router.get("/")
async def list_campaigns(
    status: str | None = Query(None),
    batch_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: str = Depends(get_current_user),
):
    """List research campaigns with optional filters."""
    async with async_session() as session:
        query = select(ResearchCampaign)
        count_query = select(func.count(ResearchCampaign.id))

        if status:
            query = query.where(ResearchCampaign.status == status)
            count_query = count_query.where(ResearchCampaign.status == status)
        if batch_id is not None:
            query = query.where(ResearchCampaign.batch_id == batch_id)
            count_query = count_query.where(ResearchCampaign.batch_id == batch_id)

        total = (await session.execute(count_query)).scalar() or 0

        campaigns = (
            await session.execute(
                query.order_by(ResearchCampaign.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
        "items": [ResearchCampaignOut.model_validate(c) for c in campaigns],
    }


@router.get("/identities")
async def get_identities(user: str = Depends(get_current_user)):
    """List available sender identities."""
    identities = list_identities()
    result = []
    for name in identities:
        try:
            data = load_identity(name)
            result.append({
                "id": name,
                "company_name": data.get("company_name", name),
                "sender_name": data.get("sender_name", ""),
                "sender_email": data.get("sender_email", ""),
                "industry": data.get("industry", ""),
            })
        except Exception:
            result.append({"id": name, "company_name": name, "error": "Failed to load"})
    return result


def _validate_identity_slug(identity_id: str) -> None:
    """Reject identity IDs that could cause path traversal."""
    if not re.match(r"^[a-zA-Z0-9_\-]+$", identity_id) or len(identity_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid identity_id: alphanumeric, hyphens, underscores only")


def _build_identity_metadata(req: IdentityRequest) -> dict:
    metadata = {
        "identity_id": req.identity_id,
        "company_name": req.company_name,
        "sender_name": req.sender_name,
        "sender_title": req.sender_title,
        "sender_email": req.sender_email,
    }
    for field in ("website", "industry", "tagline", "sender_phone", "sender_linkedin", "calendar_link"):
        val = getattr(req, field)
        if val:
            metadata[field] = val
    return metadata


@router.get("/identities/{identity_id}")
async def get_identity(identity_id: str, user: str = Depends(get_current_user)):
    """Load full identity details."""
    _validate_identity_slug(identity_id)
    try:
        data = load_identity(identity_id)
        return IdentityOut(
            identity_id=identity_id,
            company_name=data.get("company_name", ""),
            sender_name=data.get("sender_name", ""),
            sender_title=data.get("sender_title", ""),
            sender_email=data.get("sender_email", ""),
            website=data.get("website"),
            industry=data.get("industry"),
            tagline=data.get("tagline"),
            sender_phone=data.get("sender_phone"),
            sender_linkedin=data.get("sender_linkedin"),
            calendar_link=data.get("calendar_link"),
            body=data.get("body", ""),
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")


@router.post("/identities", status_code=201)
async def create_identity(req: IdentityRequest, user: str = Depends(get_current_user)):
    """Create a new sender identity."""
    existing = list_identities()
    if req.identity_id in existing:
        raise HTTPException(status_code=409, detail=f"Identity '{req.identity_id}' already exists")

    save_identity(req.identity_id, _build_identity_metadata(req), req.body)
    logger.info("Identity created: %s", req.identity_id)
    return {"id": req.identity_id, "status": "created"}


@router.put("/identities/{identity_id}")
async def update_identity(identity_id: str, req: IdentityRequest, user: str = Depends(get_current_user)):
    """Update an existing sender identity."""
    _validate_identity_slug(identity_id)
    existing = list_identities()
    if identity_id not in existing:
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")

    # Forbid renames — delete and create new instead
    if req.identity_id != identity_id:
        raise HTTPException(status_code=400, detail="Cannot rename identity_id; delete and create a new one")

    save_identity(req.identity_id, _build_identity_metadata(req), req.body)
    logger.info("Identity updated: %s", req.identity_id)
    return {"id": req.identity_id, "status": "updated"}


@router.delete("/identities/{identity_id}")
async def delete_identity(identity_id: str, user: str = Depends(get_current_user)):
    """Delete a sender identity."""
    _validate_identity_slug(identity_id)
    from src.research.identities import IDENTITIES_DIR
    path = IDENTITIES_DIR / f"{identity_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Identity '{identity_id}' not found")
    try:
        path.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete identity file: {e}")
    logger.info("Identity deleted: %s", identity_id)
    return {"id": identity_id, "status": "deleted"}


_MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_DEFAULTS_KEYS = {"goal", "identity", "language", "email_tone", "auto_reply_mode", "country", "industry"}
_SLUG_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


@router.post("/batch/import", status_code=200)
async def import_batch_csv(
    background_tasks: BackgroundTasks,
    user: str = Depends(get_current_user),
    file: UploadFile | None = File(None),
    csv_text: str | None = Form(None),
    defaults: str | None = Form(None),
    name: str | None = Form(None),
    dry_run: bool = Form(False),
):
    """Import companies from CSV (file upload or pasted text).

    When dry_run=true, returns a preview with parsed companies and warnings.
    When dry_run=false, creates a batch and starts processing.
    """
    # Get CSV content from file or text
    csv_content: str | None = None
    if file and file.filename:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only .csv files are accepted")
        raw = await file.read(_MAX_CSV_BYTES + 1)
        if len(raw) > _MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV file too large (max 5 MB)")
        try:
            csv_content = raw.decode("utf-8")
        except UnicodeDecodeError:
            csv_content = raw.decode("latin-1")
    elif csv_text:
        if len(csv_text.encode("utf-8", errors="replace")) > _MAX_CSV_BYTES:
            raise HTTPException(status_code=413, detail="CSV text too large (max 5 MB)")
        csv_content = csv_text
    else:
        raise HTTPException(status_code=400, detail="Provide either a CSV file or csv_text")

    # Parse and validate defaults JSON
    parsed_defaults: dict | None = None
    if defaults:
        try:
            parsed_defaults = json.loads(defaults)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in defaults")
        if not isinstance(parsed_defaults, dict):
            raise HTTPException(status_code=400, detail="Defaults must be a JSON object")
        unknown = set(parsed_defaults.keys()) - _ALLOWED_DEFAULTS_KEYS
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unknown defaults keys: {unknown}")
        if "identity" in parsed_defaults and not _SLUG_RE.match(str(parsed_defaults["identity"])):
            raise HTTPException(status_code=400, detail="Invalid identity in defaults")

    # Parse CSV
    result = parse_csv(csv_content, parsed_defaults)

    if result.errors:
        raise HTTPException(status_code=422, detail={
            "errors": result.errors,
            "warnings": result.warnings,
        })

    if not result.companies:
        raise HTTPException(status_code=422, detail="No valid companies found in CSV")

    # Validate through Pydantic models for field length enforcement
    validated_companies: list[dict] = []
    from src.api.schemas import BatchImportCompany
    for i, c in enumerate(result.companies):
        try:
            validated = BatchImportCompany(**c)
            validated_companies.append(validated.model_dump())
        except Exception as e:
            result.warnings.append(f"Row {i + 1} validation: {e}")

    if not validated_companies:
        raise HTTPException(status_code=422, detail="No valid companies after validation")

    # Build preview response
    preview = BatchImportPreview(
        companies=validated_companies,
        warnings=result.warnings,
        errors=result.errors,
        column_mapping=result.column_mapping,
        total=len(validated_companies),
    )

    if dry_run:
        return preview.model_dump()

    # Create and run batch
    batch_name = name or "CSV Import"
    batch_id = await create_batch(
        name=batch_name,
        companies=validated_companies,
        defaults=parsed_defaults,
    )
    background_tasks.add_task(run_batch, batch_id)

    return {
        "batch_id": batch_id,
        "status": "started",
        "total_companies": len(validated_companies),
        "warnings": result.warnings,
    }


@router.get("/batches")
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: str = Depends(get_current_user),
):
    """List research batches."""
    async with async_session() as session:
        total = (await session.execute(
            select(func.count(ResearchBatch.id))
        )).scalar() or 0

        batches = (
            await session.execute(
                select(ResearchBatch)
                .order_by(ResearchBatch.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
        "items": [ResearchBatchOut.model_validate(b) for b in batches],
    }


@router.get("/batch/{batch_id}")
async def get_batch(
    batch_id: int,
    user: str = Depends(get_current_user),
):
    """Get batch status with all campaigns."""
    try:
        return await get_batch_status(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/batch/{batch_id}/pause")
async def pause_batch_endpoint(
    batch_id: int,
    user: str = Depends(get_current_user),
):
    """Pause a running batch."""
    try:
        await pause_batch(batch_id)
        return {"status": "paused", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch/{batch_id}/resume")
async def resume_batch_endpoint(
    batch_id: int,
    user: str = Depends(get_current_user),
):
    """Resume a paused batch."""
    try:
        await resume_batch(batch_id)
        return {"status": "resumed", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch/{batch_id}/cancel")
async def cancel_batch_endpoint(
    batch_id: int,
    user: str = Depends(get_current_user),
):
    """Cancel a batch and all its queued/running campaigns."""
    try:
        await cancel_batch(batch_id)
        return {"status": "cancelled", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    user: str = Depends(get_current_user),
):
    """Get detailed info about a research campaign."""
    async with async_session() as session:
        campaign = await session.get(ResearchCampaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

    return ResearchCampaignOut.model_validate(campaign)


@router.get("/{campaign_id}/output/{filename}")
async def get_output_file(
    campaign_id: int,
    filename: str,
    user: str = Depends(get_current_user),
):
    """Get a specific research output file content."""
    async with async_session() as session:
        campaign = await session.get(ResearchCampaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

    if not campaign.output_dir:
        raise HTTPException(status_code=404, detail="No output directory set")

    # Security: only allow specific filenames to prevent path traversal
    allowed = {
        "00_input.md",
        "01_company_dossier.md",
        "02_opportunity_analysis.md",
        "03_contacts_search.md",
        "04b_person_profile.md",
        "04_peer_intelligence.md",
        "05_value_proposition_plan.md",
        "06_email_draft.md",
    }
    if filename not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid filename. Allowed: {allowed}")

    filepath = os.path.join(campaign.output_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    with open(filepath) as f:
        content = f.read()

    return {"filename": filename, "content": content}


@router.post("/{campaign_id}/cancel")
async def cancel_campaign_endpoint(
    campaign_id: int,
    user: str = Depends(get_current_user),
):
    """Cancel a running research campaign."""
    async with async_session() as session:
        campaign = await session.get(ResearchCampaign, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status in ("sent", "draft_pending", "skipped", "cancelled"):
            raise HTTPException(status_code=400, detail=f"Campaign is {campaign.status}, cannot cancel")

        # For queued campaigns, just set status directly
        if campaign.status == "queued":
            campaign.status = "cancelled"
            campaign.updated_at = datetime.now(timezone.utc)
            await session.commit()
        else:
            # Running campaign — request cancellation via in-memory flag
            request_cancel(campaign_id)
            # Also set status immediately so UI reflects it
            campaign.status = "cancelled"
            campaign.updated_at = datetime.now(timezone.utc)
            await session.commit()

    return {"status": "cancelled", "campaign_id": campaign_id}


@router.post("/{campaign_id}/skip")
async def skip_campaign_endpoint(
    campaign_id: int,
    user: str = Depends(get_current_user),
):
    """Skip a queued campaign."""
    try:
        await skip_campaign(campaign_id)
        return {"status": "skipped", "campaign_id": campaign_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{campaign_id}/retry")
async def retry_campaign_endpoint(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    user: str = Depends(get_current_user),
):
    """Retry a failed campaign."""
    try:
        await retry_campaign(campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    background_tasks.add_task(run_pipeline, campaign_id)
    return {"status": "retrying", "campaign_id": campaign_id}
