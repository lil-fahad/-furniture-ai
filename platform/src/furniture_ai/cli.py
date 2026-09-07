import argparse
import getpass
import hashlib
import json
from pathlib import Path

from sqlalchemy import delete, select

from furniture_ai.auth import PASSWORDS
from furniture_ai.config import get_settings
from furniture_ai.db import make_engine, now, sessions
from furniture_ai.jobs import ACTIVE
from furniture_ai.models import Asset, Audit, Feedback, Job, LoginSession, Project, RateBucket, Tenant, User
from furniture_ai.storage import Storage


def create_user(factory, username, password, tenant_name=None, tenant_id=None, role="admin"):
    username = username.strip().lower()
    if not 3 <= len(username) <= 120 or not 12 <= len(password) <= 256:
        raise ValueError("Username requires 3–120 characters and password requires 12–256")
    with factory.begin() as db:
        if db.scalar(select(User.id).where(User.username == username)):
            raise ValueError("Username already exists")
        tenant = db.get(Tenant, tenant_id) if tenant_id else None
        if not tenant:
            if tenant_id:
                raise ValueError("Tenant not found")
            tenant = Tenant(name=tenant_name or "Design studio")
            db.add(tenant)
            db.flush()
        user = User(tenant_id=tenant.id, username=username, password_hash=PASSWORDS.hash(password), role=role)
        db.add(user)
        db.flush()
        return {"user_id": user.id, "tenant_id": tenant.id, "username": username}


def collect_garbage(factory, storage, retention_days):
    with factory.begin() as db:
        db.execute(delete(LoginSession).where(LoginSession.expires_at < now()))
        db.execute(delete(RateBucket).where(RateBucket.expires_at < now()))
        active_projects = select(Job.project_id).where(Job.state.in_(ACTIVE))
        candidates = db.scalars(
            select(Project)
            .where(
                Project.id.not_in(active_projects),
                (Project.deleted_at.is_not(None)) | (Project.created_at < now() - retention_days * 86400),
            )
            .with_for_update(skip_locked=True)
        )
        ids = []
        for project in candidates:
            # Recheck after the project lock under READ COMMITTED; enqueue may have won the race.
            if not db.scalar(
                select(Job.id).where(Job.project_id == project.id, Job.state.in_(ACTIVE)).limit(1)
            ):
                ids.append((project.id, project.tenant_id))
        # Tombstones prevent new jobs/edits before potentially slow storage cleanup.
        for project_id, _ in ids:
            db.get(Project, project_id).deleted_at = now()
    for project_id, tenant_id in ids:
        storage.delete_prefix(f"tenants/{tenant_id}/projects/{project_id}")
        with factory.begin() as db:
            job_ids = select(Job.id).where(Job.project_id == project_id)
            db.execute(delete(Feedback).where(Feedback.job_id.in_(job_ids)))
            db.execute(delete(Job).where(Job.project_id == project_id))
            db.execute(delete(Asset).where(Asset.project_id == project_id))
            db.execute(delete(Project).where(Project.id == project_id))
            db.add(Audit(tenant_id=tenant_id, actor_id=None, action="project.purge", resource_id=project_id))
    return len(ids)


def main():
    p = argparse.ArgumentParser(prog="furniture")
    sub = p.add_subparsers(dest="command", required=True)
    user = sub.add_parser("create-user")
    user.add_argument("--username", required=True)
    group = user.add_mutually_exclusive_group()
    group.add_argument("--tenant-name")
    group.add_argument("--tenant-id")
    user.add_argument("--role", choices=["admin", "member"], default="admin")
    reset = sub.add_parser("reset-password")
    reset.add_argument("--username", required=True)
    export = sub.add_parser("export-feedback")
    export.add_argument("--tenant-id", required=True)
    export.add_argument("--output", type=Path, required=True)
    sub.add_parser("gc")
    sub.add_parser("worker")
    a = p.parse_args()
    if a.command == "worker":
        from furniture_ai.worker import main as work

        return work()
    settings = get_settings()
    engine = make_engine(settings.database_url)
    factory = sessions(engine)
    try:
        if a.command == "create-user":
            password = getpass.getpass("Password (at least 12 characters): ")
            if password != getpass.getpass("Confirm password: "):
                raise ValueError("Passwords do not match")
            print(json.dumps(create_user(factory, a.username, password, a.tenant_name, a.tenant_id, a.role)))
        elif a.command == "reset-password":
            password = getpass.getpass("New password (at least 12 characters): ")
            if not 12 <= len(password) <= 256 or password != getpass.getpass("Confirm password: "):
                raise ValueError("Passwords must match and contain 12–256 characters")
            with factory.begin() as db:
                u = db.scalar(select(User).where(User.username == a.username.lower()))
                if not u:
                    raise ValueError("User not found")
                u.password_hash = PASSWORDS.hash(password)
                db.execute(delete(LoginSession).where(LoginSession.user_id == u.id))
            print("Password changed; all previous sessions revoked.")
        elif a.command == "gc":
            print(
                json.dumps(
                    {"purged_projects": collect_garbage(factory, Storage(settings), settings.retention_days)}
                )
            )
        elif a.command == "export-feedback":
            records = []
            with factory() as db:
                rows = db.scalars(
                    select(Feedback).where(
                        Feedback.tenant_id == a.tenant_id, Feedback.consent_training.is_(True)
                    )
                )
                for f in rows:
                    job = db.get(Job, f.job_id)
                    project = db.get(Project, job.project_id)
                    if project.deleted_at:
                        continue
                    variants = {v["index"]: v for v in job.result["variants"]}
                    records.append(
                        {
                            "id": f.id,
                            "group_id": hashlib.sha256(job.project_id.encode()).hexdigest(),
                            "winner": variants[f.winner]["features"],
                            "loser": variants[f.loser]["features"],
                            "source": "consented-first-party-preference",
                            "license": "first-party-permission",
                            "training_use": True,
                            "commercial_use": True,
                            "consent": True,
                        }
                    )
            a.output.parent.mkdir(parents=True, exist_ok=True)
            a.output.write_text("".join(json.dumps(r) + "\n" for r in records))
            print(json.dumps({"exported_consented_preferences": len(records)}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
