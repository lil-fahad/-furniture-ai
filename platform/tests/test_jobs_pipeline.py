import base64
import io

import pytest
from PIL import Image
from sqlalchemy import update

from furniture_ai.db import now
from furniture_ai.errors import DomainError, LeaseLost
from furniture_ai.jobs import checkpoint, claim, finish, heartbeat
from furniture_ai.models import Job
from furniture_ai.pipeline import Pipeline


def start(client, project):
    return client.post(
        f"/api/projects/{project['id']}/jobs",
        json={"kind": "design"},
        headers={"idempotency-key": "pipeline-test-0001"},
    ).json()


def test_lease_reclaim_fences_old_worker(system, client, project):
    start(client, project)
    factory, settings = system[2:4]
    old = claim(factory, settings)
    assert old and claim(factory, settings) is None
    assert heartbeat(factory, old.id, old.lease_token, settings)
    with factory.begin() as db:
        db.execute(update(Job).where(Job.id == old.id).values(lease_until=now() - 1))
    fresh = claim(factory, settings)
    assert fresh.lease_token != old.lease_token and fresh.attempts == 2
    assert not heartbeat(factory, old.id, old.lease_token, settings)
    with pytest.raises(LeaseLost):
        checkpoint(factory, old.id, old.lease_token, "stale", {})
    with pytest.raises(LeaseLost):
        finish(factory, old, result={}, settings=settings)


def test_cancel_fences_inflight_worker(system, client, project):
    start(client, project)
    factory, settings = system[2:4]
    job = claim(factory, settings)
    client.post(f"/api/jobs/{job.id}/cancel")
    with pytest.raises(LeaseLost):
        finish(factory, job, result={}, settings=settings)


class FixtureProviders:
    """Tests substitute ONLY the remote model boundary. Never used in the application."""

    def __init__(self, png):
        self.png = base64.b64encode(png).decode()
        mask = io.BytesIO()
        Image.new("L", (64, 48), 255).save(mask, "PNG")
        self.mask = base64.b64encode(mask.getvalue()).decode()
        self.calls = []
        self.fail_once = True

    def analyze(self, image, kind):
        self.calls.append("analyze")
        return {
            "room_type": "living_room",
            "description": "Test fixture",
            "observed_features": [],
            "palette": [],
            "suggested_width_m": None,
            "suggested_length_m": None,
            "dimension_evidence": "none",
            "uncertainties": [],
        }

    def evaluate(self, *args):
        return {
            "style_alignment": 0.6,
            "visual_quality": 0.7,
            "requirement_match": 0.5,
            "structural_consistency": 0.8,
            "concerns": [],
            "explanation": "Test fixture",
        }

    def model(self, service, operation, payload):
        self.calls.append(operation)
        if operation == "perceive":
            return {"mask": self.mask, "depth": self.png, "objects": [], "models": {"test": "fixture"}}
        if operation == "generate":
            if self.fail_once:
                self.fail_once = False
                raise DomainError("PROVIDER_BUSY", "Fixture transient failure", 503, True)
            return {"image": self.png, "metadata": {"model": "test-fixture"}}
        if operation == "similarity":
            return {"score": 0.6, "revision": "test-fixture"}
        raise AssertionError(operation)


def test_pipeline_resumes_stages_and_exports(system, client, project, png):
    start(client, project)
    app, _, factory, settings, _ = system
    providers = FixtureProviders(png)
    pipeline = Pipeline(settings, app.state.storage, providers)
    job = claim(factory, settings)

    def save(name, value):
        checkpoint(factory, job.id, job.lease_token, name, value)

    with pytest.raises(DomainError) as failure:
        pipeline.run(job, save)
    finish(factory, job, error=failure.value, settings=settings)
    with factory.begin() as db:
        db.execute(update(Job).where(Job.id == job.id).values(available_at=0))
    job = claim(factory, settings)
    result = pipeline.run(job, save)
    finish(factory, job, result=result, settings=settings)
    assert providers.calls.count("analyze") == 1 and providers.calls.count("perceive") == 1
    r = client.get(f"/api/jobs/{job.id}")
    assert r.json()["state"] == "succeeded"
    assert "tenants/" not in r.text
    assert r.json()["result"]["supplier_status"] == "deferred"
    for artifact in r.json()["result"]["artifacts"].values():
        assert client.get(artifact["url"]).status_code == 200
    assert "sofa" in client.get(f"/api/jobs/{job.id}/export?format=csv").text
    assert client.post(f"/api/jobs/{job.id}/feedback", json={"winner": 0, "loser": 1}).status_code == 422
