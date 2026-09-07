import csv
import hashlib
import io
import json
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CollectorRegistry, Gauge, generate_latest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from furniture_ai.auth import (
    COOKIE,
    DUMMY_HASH,
    PASSWORDS,
    audit,
    check_password,
    current_user,
    digest,
    rate_limit,
    require_origin,
)
from furniture_ai.config import get_settings
from furniture_ai.db import make_engine, now, sessions, uid
from furniture_ai.errors import DomainError
from furniture_ai.jobs import ACTIVE, enqueue, ensure_idle, project_for
from furniture_ai.middleware import SecurityMiddleware
from furniture_ai.models import Asset, Feedback, Job, LoginSession, Project, User
from furniture_ai.schemas import FeedbackInput, JobCreate, Login, ProjectCreate, ProjectUpdate
from furniture_ai.storage import Storage, sanitize_image

Actor = Annotated[User, Depends(current_user)]


def public_project(p):
    return {
        k: getattr(p, k)
        for k in ("id", "title", "preferences", "geometry", "analysis", "revision", "created_at")
    }


def public_job(job):
    result = json.loads(json.dumps(job.result)) if job.result else None
    if result and "artifacts" in result:
        result["artifacts"] = {
            name: {"url": f"/api/jobs/{job.id}/artifacts/{name}", "mime": a["mime"], "sha256": a["sha256"]}
            for name, a in result["artifacts"].items()
        }
    return {
        "id": job.id,
        "project_id": job.project_id,
        "kind": job.kind,
        "state": job.state,
        "attempts": job.attempts,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "completed_stages": list(job.checkpoint or {}),
        "result": result,
        "error": {"code": job.error_code, "message": job.error_message} if job.error_code else None,
    }


def job_for(db, user, job_id, lock=False):
    query = (
        select(Job)
        .join(Project, Project.id == Job.project_id)
        .where(Job.id == job_id, Job.tenant_id == user.tenant_id, Project.deleted_at.is_(None))
    )
    job = db.scalar(query.with_for_update(of=Job) if lock else query)
    if not job:
        raise DomainError("NOT_FOUND", "Job not found.", 404)
    return job


def create_app(settings=None, engine=None):
    settings = settings or get_settings()
    engine = engine or make_engine(settings.database_url)
    factory = sessions(engine)

    @asynccontextmanager
    async def lifespan(_):
        yield
        engine.dispose()

    app = FastAPI(
        title="Furniture AI",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.state.settings, app.state.sessions = settings, factory
    app.state.storage = Storage(settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(
        SecurityMiddleware,
        max_bytes=settings.max_upload_bytes + 65536,
        production=settings.environment == "production",
    )

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse(
            {"error": {"code": error.code, "message": error.message}, "request_id": request.state.request_id},
            status_code=error.status,
            headers={"Retry-After": "60"} if error.status == 429 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        fields = [".".join(map(str, e["loc"])) for e in error.errors()]
        return JSONResponse(
            {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Check these fields: " + ", ".join(fields)[:500],
                },
                "request_id": request.state.request_id,
            },
            status_code=422,
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request, _):
        return JSONResponse(
            {
                "error": {"code": "CONFLICT", "message": "A concurrent change conflicted. Retry."},
                "request_id": request.state.request_id,
            },
            status_code=409,
        )

    @app.exception_handler(Exception)
    async def unexpected(request, error):
        import logging

        logging.getLogger("furniture.api").error(
            json.dumps({"request_id": request.state.request_id, "error_type": type(error).__name__})
        )
        return JSONResponse(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Request failed. Use the request ID when contacting support.",
                },
                "request_id": request.state.request_id,
            },
            status_code=500,
        )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            with factory() as db:
                db.execute(text("SELECT 1"))
                if settings.environment != "test":
                    if db.scalar(text("SELECT version_num FROM alembic_version")) != "0001":
                        raise RuntimeError("Migration mismatch")
            return {"status": "ready"}
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)

    @app.get("/metrics")
    def metrics(request: Request):
        token = settings.metrics_token.get_secret_value()
        if not token or not secrets.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + token
        ):
            raise DomainError("FORBIDDEN", "Metrics authentication required.", 403)
        registry = CollectorRegistry()
        gauge = Gauge("furniture_jobs", "Jobs by state", ["state"], registry=registry)
        age = Gauge("furniture_oldest_pending_seconds", "Age of oldest pending job", registry=registry)
        with factory() as db:
            for state, count in db.execute(select(Job.state, func.count()).group_by(Job.state)):
                gauge.labels(state=state).set(count)
            oldest = db.scalar(select(func.min(Job.created_at)).where(Job.state.in_(ACTIVE)))
            age.set(max(0, now() - oldest) if oldest else 0)
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    @app.post("/api/auth/login")
    def login(body: Login, request: Request):
        require_origin(request)
        ip = request.client.host if request.client else "unknown"
        username = body.username.strip().lower()
        rate_limit(factory, "login-ip:" + ip, 30, 900)
        rate_limit(factory, "login-name:" + username, 10, 900)
        with factory.begin() as db:
            user = db.scalar(select(User).where(User.username == username))
            valid = check_password(user.password_hash if user else DUMMY_HASH, body.password)
            if not valid or not user or not user.active:
                raise DomainError("LOGIN_FAILED", "Incorrect username or password.", 401)
            if PASSWORDS.check_needs_rehash(user.password_hash):
                user.password_hash = PASSWORDS.hash(body.password)
            token = secrets.token_urlsafe(48)
            previous = request.cookies.get(COOKIE)
            if previous:
                db.execute(delete(LoginSession).where(LoginSession.token_hash == digest(previous)))
            db.add(
                LoginSession(
                    token_hash=digest(token),
                    user_id=user.id,
                    expires_at=now() + settings.session_hours * 3600,
                )
            )
            audit(db, user, "login", user.id)
        response = JSONResponse({"username": user.username, "role": user.role})
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=settings.environment == "production",
            samesite="strict",
            max_age=settings.session_hours * 3600,
            path="/",
        )
        return response

    @app.post("/api/auth/logout")
    def logout(request: Request, user: Actor):
        with factory.begin() as db:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == digest(request.cookies[COOKIE])))
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/api/me")
    def me(user: Actor):
        from furniture_ai.layout import DEFAULT_SIZES

        return {
            "username": user.username,
            "role": user.role,
            "layout_mode": settings.layout_mode,
            "ranking_mode": settings.ranking_mode,
            "supplier_status": "deferred",
            "default_sizes": DEFAULT_SIZES,
        }

    @app.get("/api/projects")
    def list_projects(user: Actor, offset: int = 0, limit: int = 40):
        if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
            raise DomainError("PAGINATION", "Invalid pagination bounds.")
        with factory() as db:
            items = db.scalars(
                select(Project)
                .where(Project.tenant_id == user.tenant_id, Project.deleted_at.is_(None))
                .order_by(Project.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            return [public_project(p) for p in items]

    @app.post("/api/projects", status_code=201)
    def create_project(body: ProjectCreate, user: Actor):
        rate_limit(factory, "projects:" + user.tenant_id, 100, 86400)
        with factory.begin() as db:
            p = Project(
                tenant_id=user.tenant_id,
                title=body.title,
                preferences=body.preferences.model_dump(),
                geometry=body.geometry.model_dump() if body.geometry else None,
            )
            db.add(p)
            db.flush()
            audit(db, user, "project.create", p.id)
        return public_project(p)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str, user: Actor):
        with factory() as db:
            p = project_for(db, user.tenant_id, project_id)
            assets = db.scalars(select(Asset).where(Asset.project_id == p.id).order_by(Asset.created_at))
            jobs = db.scalars(
                select(Job).where(Job.project_id == p.id).order_by(Job.created_at.desc()).limit(30)
            )
            return {
                **public_project(p),
                "assets": [
                    {
                        "id": a.id,
                        "kind": a.kind,
                        "source_id": a.source_id,
                        "width": a.width,
                        "height": a.height,
                        "url": f"/api/assets/{a.id}",
                    }
                    for a in assets
                ],
                "jobs": [public_job(j) for j in jobs],
            }

    @app.patch("/api/projects/{project_id}")
    def edit_project(project_id: str, body: ProjectUpdate, user: Actor):
        with factory.begin() as db:
            p = project_for(db, user.tenant_id, project_id, lock=True)
            ensure_idle(db, p.id)
            if p.revision != body.revision:
                raise DomainError("REVISION_CONFLICT", "Reload the project before saving changes.", 409)
            for key, value in body.model_dump(exclude_unset=True, exclude={"revision"}).items():
                if value is not None:
                    setattr(p, key, value)
            p.revision += 1
            audit(db, user, "project.update", p.id)
        return public_project(p)

    @app.delete("/api/projects/{project_id}", status_code=204)
    def delete_project(project_id: str, user: Actor):
        with factory.begin() as db:
            p = project_for(db, user.tenant_id, project_id, lock=True)
            p.deleted_at = now()
            db.execute(
                update(Job)
                .where(Job.project_id == p.id, Job.state.in_(ACTIVE))
                .values(state="cancelled", lease_token=None, lease_until=None, finished_at=now())
            )
            audit(db, user, "project.delete", p.id)

    @app.post("/api/projects/{project_id}/assets", status_code=201)
    def upload(
        project_id: str,
        user: Actor,
        file: Annotated[UploadFile, File()],
        kind: Literal["photo", "floor_plan", "mask"] = "photo",
        page: int = 0,
    ):
        if not 0 <= page < 20:
            raise DomainError("PAGE_NUMBER", "PDF page must be between 0 and 19.")
        with factory() as db:
            project_for(db, user.tenant_id, project_id)
        raw = file.file.read(settings.max_upload_bytes + 1)
        data, width, height, mime = sanitize_image(raw, settings, kind, page)
        with factory.begin() as db:
            p = project_for(db, user.tenant_id, project_id, lock=True)
            ensure_idle(db, p.id)
            if db.scalar(select(func.count()).select_from(Asset).where(Asset.project_id == p.id)) >= 20:
                raise DomainError("ASSET_LIMIT", "A project can contain at most 20 uploads.", 409)
            source = db.scalar(
                select(Asset)
                .where(Asset.project_id == p.id, Asset.kind != "mask")
                .order_by(Asset.created_at.desc(), Asset.id.desc())
                .limit(1)
            )
            if kind == "mask" and (
                not source or source.kind != "photo" or (width, height) != (source.width, source.height)
            ):
                raise DomainError("MASK_DIMENSIONS", "The mask must match the latest room photo dimensions.")
            asset_id = uid()
            key = f"tenants/{user.tenant_id}/projects/{p.id}/uploads/{asset_id}." + (
                "png" if kind == "mask" else "jpg"
            )
            app.state.storage.put(key, data, mime)
            asset = Asset(
                id=asset_id,
                tenant_id=user.tenant_id,
                project_id=p.id,
                object_key=key,
                sha256=hashlib.sha256(data).hexdigest(),
                width=width,
                height=height,
                kind=kind,
                source_id=source.id if kind == "mask" else None,
            )
            db.add(asset)
            p.revision += 1
            if kind != "mask":
                p.analysis = None
            audit(db, user, "asset.upload", asset_id)
        return {
            "id": asset_id,
            "url": f"/api/assets/{asset_id}",
            "width": width,
            "height": height,
            "revision": p.revision,
        }

    @app.get("/api/assets/{asset_id}")
    def get_asset(asset_id: str, user: Actor):
        with factory() as db:
            a = db.scalar(
                select(Asset)
                .join(Project)
                .where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id, Project.deleted_at.is_(None))
            )
            if not a:
                raise DomainError("NOT_FOUND", "Image not found.", 404)
            return Response(
                app.state.storage.get(a.object_key),
                media_type="image/png" if a.kind == "mask" else "image/jpeg",
            )

    @app.post("/api/projects/{project_id}/jobs", status_code=202)
    def start_job(
        project_id: str,
        body: JobCreate,
        user: Actor,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")],
    ):
        rate_limit(factory, "jobs:" + user.tenant_id, settings.jobs_per_hour, 3600)
        with factory.begin() as db:
            job = enqueue(db, user, project_id, body.kind, idempotency_key, settings)
            audit(db, user, "job.enqueue", job.id)
        return public_job(job)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, user: Actor):
        with factory() as db:
            return public_job(job_for(db, user, job_id))

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, user: Actor):
        with factory.begin() as db:
            job = job_for(db, user, job_id, lock=True)
            if job.state in ACTIVE:
                job.state, job.lease_token, job.lease_until = "cancelled", None, None
                job.finished_at = now()
            audit(db, user, "job.cancel", job.id)
        return public_job(job)

    @app.get("/api/jobs/{job_id}/artifacts/{name}")
    def get_artifact(job_id: str, name: str, user: Actor):
        with factory() as db:
            job = job_for(db, user, job_id)
            a = (job.result or {}).get("artifacts", {}).get(name)
            if job.state != "succeeded" or not a:
                raise DomainError("NOT_FOUND", "Artifact not found.", 404)
            return Response(app.state.storage.get(a["key"]), media_type=a["mime"])

    @app.get("/api/jobs/{job_id}/export")
    def export(job_id: str, user: Actor, format: Literal["json", "csv"] = "json"):
        with factory() as db:
            job = job_for(db, user, job_id)
            if job.state != "succeeded":
                raise DomainError("NOT_READY", "Wait until the job finishes.", 409)
            result = public_job(job)
        if format == "json":
            content, mime = json.dumps(result, indent=2, ensure_ascii=False), "application/json"
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                [
                    "proposal",
                    "piece",
                    "category",
                    "x_m",
                    "y_m",
                    "width_m",
                    "depth_m",
                    "rotation",
                    "dimension_source",
                ]
            )
            for v in result["result"].get("variants", []):
                for p in v["layout"]["pieces"]:
                    writer.writerow(
                        [
                            v["index"],
                            p["id"],
                            p["category"],
                            p["x"],
                            p["y"],
                            p["width_m"],
                            p["depth_m"],
                            p["rotation"],
                            p["dimension_source"],
                        ]
                    )
            content, mime = output.getvalue(), "text/csv"
        return Response(
            content,
            media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="design-{job_id}.{format}"'},
        )

    @app.post("/api/jobs/{job_id}/feedback", status_code=201)
    def feedback(job_id: str, body: FeedbackInput, user: Actor):
        with factory.begin() as db:
            job = job_for(db, user, job_id, lock=True)
            indices = {v["index"] for v in (job.result or {}).get("variants", [])}
            if job.state != "succeeded" or not {body.winner, body.loser} <= indices:
                raise DomainError("INVALID_PREFERENCE", "Choose two finished proposals from this job.")
            previous = db.scalar(
                select(Feedback).where(Feedback.job_id == job_id, Feedback.user_id == user.id)
            )
            if previous:
                previous.winner, previous.loser = body.winner, body.loser
                previous.consent_training = body.consent_training
            else:
                db.add(
                    Feedback(tenant_id=user.tenant_id, user_id=user.id, job_id=job_id, **body.model_dump())
                )
            audit(db, user, "feedback.save", job.id)
        return {"saved": True}

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    return app


app = create_app()
