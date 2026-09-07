import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from furniture_ai.api import create_app
from furniture_ai.cli import create_user
from furniture_ai.config import Settings
from furniture_ai.db import Base, make_engine, sessions


@pytest.fixture
def system(tmp_path):
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=tmp_path / "objects",
        vision_revision="test-fixture-v1",
    )
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    factory = sessions(engine)
    users = [create_user(factory, name, "Test-password-12345", tenant_name=name) for name in ["alice", "bob"]]
    app = create_app(settings, engine)
    with TestClient(app, headers={"origin": settings.public_origin}) as client:
        yield app, client, factory, settings, users


@pytest.fixture
def client(system):
    client = system[1]
    assert (
        client.post(
            "/api/auth/login", json={"username": "alice", "password": "Test-password-12345"}
        ).status_code
        == 200
    )
    return client


@pytest.fixture
def png():
    b = io.BytesIO()
    Image.new("RGB", (64, 48), "#c5b9a3").save(b, "PNG")
    return b.getvalue()


@pytest.fixture
def geometry():
    return {
        "boundary": [{"x": 0, "y": 0}, {"x": 5, "y": 0}, {"x": 5, "y": 4}, {"x": 0, "y": 4}],
        "keepouts": [],
        "access_points": [],
        "confirmed": True,
    }


@pytest.fixture
def project(client, png, geometry):
    r = client.post(
        "/api/projects",
        json={
            "title": "Room",
            "geometry": geometry,
            "preferences": {"requirements": [{"category": "sofa"}], "variants": 1},
        },
    )
    assert r.status_code == 201, r.text
    p = r.json()
    r = client.post(
        f"/api/projects/{p['id']}/assets?kind=photo", files={"file": ("room.png", png, "image/png")}
    )
    assert r.status_code == 201, r.text
    return client.get(f"/api/projects/{p['id']}").json()
