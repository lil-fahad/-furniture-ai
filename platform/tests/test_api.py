import io

from PIL import Image

from furniture_ai.cli import collect_garbage
from furniture_ai.models import Asset


def enqueue(client, project, key="test-request-001", kind="design"):
    return client.post(
        f"/api/projects/{project['id']}/jobs", headers={"idempotency-key": key}, json={"kind": kind}
    )


def test_tenant_isolation_across_project_asset_job(client, project):
    job = enqueue(client, project).json()
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "bob", "password": "Test-password-12345"})
    paths = [f"/api/projects/{project['id']}", project["assets"][0]["url"], f"/api/jobs/{job['id']}"]
    for path in paths:
        assert client.get(path).status_code == 404
    assert client.get("/api/projects").json() == []
    assert client.delete(paths[0]).status_code == 404


def test_origin_and_session_controls(client, project):
    assert client.cookies.get("furniture_session")
    r = client.patch(
        f"/api/projects/{project['id']}",
        headers={"origin": "https://evil.invalid"},
        json={"revision": project["revision"], "title": "changed"},
    )
    assert r.status_code == 403
    assert client.get("/").headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in client.get("/").headers["content-security-policy"]
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401


def test_idempotency_revision_and_busy(client, project):
    first = enqueue(client, project)
    assert first.status_code == 202, first.text
    assert enqueue(client, project).json()["id"] == first.json()["id"]
    assert enqueue(client, project, "test-request-002").status_code == 409
    assert enqueue(client, project, kind="analyze").status_code == 409
    assert (
        client.patch(
            f"/api/projects/{project['id']}", json={"revision": project["revision"], "title": "Busy"}
        ).status_code
        == 409
    )
    assert client.post(f"/api/jobs/{first.json()['id']}/cancel").json()["state"] == "cancelled"
    assert (
        client.patch(f"/api/projects/{project['id']}", json={"revision": 1, "title": "Stale"}).status_code
        == 409
    )


def test_image_limits_masks_and_metadata(client, project, png, system):
    path = f"/api/projects/{project['id']}/assets"
    assert client.post(path, files={"file": ("bad.png", b"not image", "image/png")}).status_code == 422
    assert (
        client.post(path, files={"file": ("big.png", b"x" * (12 * 1024 * 1024 + 1), "image/png")}).status_code
        == 413
    )
    wrong = io.BytesIO()
    Image.new("RGB", (32, 32)).save(wrong, "PNG")
    assert (
        client.post(
            path + "?kind=mask", files={"file": ("mask.png", wrong.getvalue(), "image/png")}
        ).status_code
        == 422
    )
    assert client.post(path + "?kind=mask", files={"file": ("mask.png", png, "image/png")}).status_code == 201
    image = Image.open(io.BytesIO(client.get(project["assets"][0]["url"]).content))
    assert image.format == "JPEG" and not image.getexif()
    with system[2]() as db:
        a = db.get(Asset, project["assets"][0]["id"])
        assert a.object_key.startswith(f"tenants/{system[4][0]['tenant_id']}/projects/{project['id']}/")


def test_invalid_json_does_not_echo_sensitive_body(client):
    r = client.post("/api/projects", json={"title": "Room", "password": "secret-marker"})
    assert r.status_code == 422 and "secret-marker" not in r.text


def test_deletion_revokes_and_purges(client, project, system):
    job = enqueue(client, project).json()
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404
    assert client.get(project["assets"][0]["url"]).status_code == 404
    assert collect_garbage(system[2], system[0].state.storage, 30) == 1
    assert not list(system[3].data_dir.rglob("*.jpg"))


def test_geometry_confirmation_required(client, png):
    p = client.post("/api/projects", json={"title": "Unmeasured"}).json()
    client.post(f"/api/projects/{p['id']}/assets", files={"file": ("room.png", png, "image/png")})
    r = enqueue(client, p)
    assert r.status_code == 422 and r.json()["error"]["code"] == "GEOMETRY_REQUIRED"
