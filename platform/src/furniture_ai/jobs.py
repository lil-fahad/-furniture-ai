import hashlib
import json

from sqlalchemy import and_, func, or_, select, update

from furniture_ai.db import now, uid
from furniture_ai.errors import DomainError, LeaseLost
from furniture_ai.models import Asset, Job, Project, Tenant

ACTIVE = ("queued", "running")


def clock(db):
    if db.bind.dialect.name == "postgresql":
        return float(db.scalar(select(func.extract("epoch", func.clock_timestamp()))))
    return now()


def project_for(db, tenant_id, project_id, lock=False):
    query = select(Project).where(
        Project.id == project_id, Project.tenant_id == tenant_id, Project.deleted_at.is_(None)
    )
    project = db.scalar(query.with_for_update() if lock else query)
    if not project:
        raise DomainError("NOT_FOUND", "Project not found.", 404)
    return project


def ensure_idle(db, project_id):
    if db.scalar(select(Job.id).where(Job.project_id == project_id, Job.state.in_(ACTIVE)).limit(1)):
        raise DomainError(
            "PROJECT_BUSY", "Wait for or cancel the current job before editing this project.", 409
        )


def enqueue(db, user, project_id, kind, key, settings):
    # Locking the tenant serializes the per-tenant queue limit and idempotency writes.
    db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).with_for_update())
    project = project_for(db, user.tenant_id, project_id, lock=True)
    request_hash = hashlib.sha256(
        json.dumps(
            {"project": project_id, "kind": kind, "revision": project.revision}, sort_keys=True
        ).encode()
    ).hexdigest()
    existing = db.scalar(select(Job).where(Job.tenant_id == user.tenant_id, Job.idempotency_key == key))
    if existing:
        if existing.request_hash != request_hash:
            raise DomainError("IDEMPOTENCY_CONFLICT", "This key belongs to a different project request.", 409)
        return existing
    ensure_idle(db, project_id)
    count = db.scalar(
        select(func.count()).select_from(Job).where(Job.tenant_id == user.tenant_id, Job.state.in_(ACTIVE))
    )
    if count >= settings.max_pending_per_tenant:
        raise DomainError("QUEUE_FULL", "Your workspace has reached its pending-job limit.", 429)
    asset = db.scalar(
        select(Asset)
        .where(Asset.project_id == project_id, Asset.kind != "mask")
        .order_by(Asset.created_at.desc(), Asset.id.desc())
        .limit(1)
    )
    if not asset:
        raise DomainError("IMAGE_REQUIRED", "Upload a room photo or floor plan first.")
    mask = db.scalar(
        select(Asset)
        .where(Asset.project_id == project_id, Asset.kind == "mask", Asset.source_id == asset.id)
        .order_by(Asset.created_at.desc(), Asset.id.desc())
        .limit(1)
    )
    if kind == "design" and (not project.geometry or not project.geometry.get("confirmed")):
        raise DomainError("GEOMETRY_REQUIRED", "Confirm the room boundary and dimensions first.")
    job = Job(
        tenant_id=user.tenant_id,
        project_id=project_id,
        kind=kind,
        idempotency_key=key,
        request_hash=request_hash,
        input={
            "asset_id": asset.id,
            "image_key": asset.object_key,
            "mask_key": mask.object_key if mask else None,
            "kind": asset.kind,
            "geometry": project.geometry,
            "preferences": project.preferences,
            "revision": project.revision,
            "analysis": project.analysis,
            "vision_revision": settings.vision_revision,
            "layout_mode": settings.layout_mode,
            "ranking_mode": settings.ranking_mode,
        },
        checkpoint={},
    )
    db.add(job)
    db.flush()
    return job


def claim(factory, settings):
    with factory.begin() as db:
        stamp = clock(db)
        db.execute(
            update(Job)
            .where(Job.state == "running", Job.lease_until < stamp, Job.attempts >= settings.max_attempts)
            .values(
                state="failed",
                error_code="RETRIES_EXHAUSTED",
                error_message="Worker did not complete within the retry limit.",
                finished_at=stamp,
                lease_token=None,
                lease_until=None,
            )
        )
        ready = or_(
            and_(Job.state == "queued", Job.available_at <= stamp),
            and_(Job.state == "running", Job.lease_until < stamp),
        )
        query = select(Job).where(ready, Job.attempts < settings.max_attempts).order_by(Job.created_at)
        job = db.scalar(query.with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        job.state = "running"
        job.attempts += 1
        job.lease_token = uid()
        job.lease_until = stamp + settings.lease_seconds
        job.error_code, job.error_message = None, None
        return job


def heartbeat(factory, job_id, token, settings):
    with factory.begin() as db:
        stamp = clock(db)
        result = db.execute(
            update(Job)
            .where(
                Job.id == job_id, Job.lease_token == token, Job.state == "running", Job.lease_until > stamp
            )
            .values(lease_until=stamp + settings.lease_seconds)
        )
        return result.rowcount == 1


def checkpoint(factory, job_id, token, stage, value):
    with factory.begin() as db:
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.state != "running" or job.lease_token != token or job.lease_until <= clock(db):
            raise LeaseLost
        job.checkpoint = {**job.checkpoint, stage: value}


def finish(factory, claimed, result=None, error=None, settings=None):
    with factory.begin() as db:
        # Same project -> job lock order as API mutations.
        project = db.scalar(select(Project).where(Project.id == claimed.project_id).with_for_update())
        job = db.scalar(select(Job).where(Job.id == claimed.id).with_for_update())
        stamp = clock(db)
        if (
            not project
            or project.deleted_at
            or not job
            or job.state != "running"
            or job.lease_token != claimed.lease_token
            or job.lease_until <= stamp
        ):
            raise LeaseLost
        if error:
            job.error_code, job.error_message = error.code, error.message[:400]
            if error.retryable and job.attempts < settings.max_attempts:
                job.state = "queued"
                job.available_at = stamp + min(60, 2**job.attempts * 3)
            else:
                job.state = "failed"
                job.finished_at = stamp
        else:
            job.result, job.state, job.finished_at = result, "succeeded", stamp
            if project.revision == job.input["revision"]:
                project.analysis = result.get("analysis")
        job.lease_until, job.lease_token = None, None
