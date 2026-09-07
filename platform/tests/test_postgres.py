"""Requires an isolated disposable database; CI supplies PostgreSQL 17."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text

from furniture_ai.config import Settings
from furniture_ai.db import Base, make_engine, sessions, uid
from furniture_ai.jobs import claim, enqueue
from furniture_ai.models import Asset, Job, Project, Tenant, User
from furniture_ai.schemas import Preferences

pytestmark = pytest.mark.postgres


@pytest.fixture
def pg():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is required for real concurrency validation")
    engine = make_engine(url)
    schema = "test_" + uid().replace("-", "")
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    factory = sessions(isolated)
    try:
        yield factory, Settings(_env_file=None)
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_concurrent_claims_are_unique(pg):
    factory, settings = pg
    with factory.begin() as db:
        t = Tenant(name="Concurrency test")
        db.add(t)
        db.flush()
        p = Project(tenant_id=t.id, title="Room", preferences={})
        db.add(p)
        db.flush()
        for i in range(12):
            db.add(
                Job(
                    tenant_id=t.id,
                    project_id=p.id,
                    kind="analyze",
                    idempotency_key=f"key-{i}",
                    request_hash=str(i),
                    input={},
                    checkpoint={},
                )
            )
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(lambda _: claim(factory, settings), range(16)))
    ids = [j.id for j in jobs if j]
    assert len(ids) == 12 and len(set(ids)) == 12


def test_concurrent_enqueue_is_idempotent(pg):
    factory, settings = pg
    with factory.begin() as db:
        t = Tenant(name="Concurrent enqueue")
        db.add(t)
        db.flush()
        user = User(tenant_id=t.id, username="test", password_hash="unused")
        p = Project(tenant_id=t.id, title="Room", preferences=Preferences().model_dump())
        db.add_all([user, p])
        db.flush()
        db.add(
            Asset(
                tenant_id=t.id,
                project_id=p.id,
                kind="photo",
                object_key="test/photo.jpg",
                sha256="0" * 64,
                width=64,
                height=48,
            )
        )

    def submit(_):
        with factory.begin() as db:
            return enqueue(db, user, p.id, "analyze", "concurrent-same-key", settings).id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(submit, range(8)))
    assert len(set(ids)) == 1
