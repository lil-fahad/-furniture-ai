import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from furniture_ai.api import create_app
from furniture_ai.db import make_engine, sessions
from furniture_ai.models import User


def test_desktop_initialization_migrates_database_and_preserves_account(tmp_path):
    from furniture_ai.desktop import initialize_desktop

    settings, env = initialize_desktop(tmp_path, "fahad", "Local-password-12345", 8910, 8911)
    assert settings.public_origin == "http://localhost:8910"
    assert settings.perception_url == settings.generation_url == settings.scoring_url
    assert env["FURNITURE_ML_ROLE"] == "all"
    engine = make_engine(settings.database_url)
    with sessions(engine)() as db:
        original = db.scalar(select(User).where(User.username == "fahad"))
        original_id, original_hash = original.id, original.password_hash
    with TestClient(
        create_app(settings, engine),
        base_url=settings.public_origin,
        headers={"origin": settings.public_origin},
    ) as client:
        result = client.post(
            "/api/auth/login", json={"username": "fahad", "password": "Local-password-12345"}
        )
        assert result.status_code == 200
        assert client.get("/api/projects").status_code == 200
    settings2, env2 = initialize_desktop(tmp_path, "fahad", "Local-password-12345", 8910, 8911)
    assert env2["FURNITURE_MODEL_API_KEY"] == env["FURNITURE_MODEL_API_KEY"]
    engine = make_engine(settings2.database_url)
    with sessions(engine)() as db:
        saved = db.scalar(select(User).where(User.username == "fahad"))
        assert saved.id == original_id and saved.password_hash == original_hash
    engine.dispose()
    assert "Local-password-12345" not in (tmp_path / "desktop-config.json").read_text()


def test_desktop_rejects_wrong_password_without_resetting_account(tmp_path):
    from furniture_ai.desktop import initialize_desktop

    initialize_desktop(tmp_path, "fahad", "Local-password-12345", 8910, 8911)
    with pytest.raises(ValueError, match="password"):
        initialize_desktop(tmp_path, "fahad", "Wrong-password-54321", 8910, 8911)
    initialize_desktop(tmp_path, "fahad", "Local-password-12345", 8910, 8911)


def test_desktop_rejects_invalid_account_before_creating_data(tmp_path):
    from furniture_ai.desktop import initialize_desktop

    with pytest.raises(ValueError):
        initialize_desktop(tmp_path / "data", "fahad", "short", 8910, 8911)
    assert not (tmp_path / "data").exists()


def test_desktop_configuration_does_not_inherit_remote_services(tmp_path, monkeypatch):
    from furniture_ai.desktop import initialize_desktop

    monkeypatch.setenv("FURNITURE_DATABASE_URL", "postgresql+psycopg://invalid/remote")
    monkeypatch.setenv("FURNITURE_VISION_URL", "https://example.com/v1")
    monkeypatch.setenv("FURNITURE_STORAGE_BACKEND", "s3")
    settings, env = initialize_desktop(tmp_path, "fahad", "Local-password-12345", 8910, 8911)
    assert settings.storage_backend == "local"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.vision_url == "http://127.0.0.1:8911/v1"
    assert json.loads(env["FURNITURE_ALLOWED_HOSTS"]) == ["localhost", "127.0.0.1"]


def test_native_server_process_login_and_upload(tmp_path, png):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    model_port = 8766 if port != 8766 else 8767
    password = "Local-process-test-12345"
    flags = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    log_path = tmp_path / "process.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "furniture_ai.desktop",
                "--credentials-stdin",
                "--api-only",
                "--no-browser",
                "--data-root",
                str(tmp_path / "native-data"),
                "--port",
                str(port),
                "--model-port",
                str(model_port),
            ],
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1"},
            **flags,
        )
        process.stdin.write(json.dumps({"username": "native-user", "password": password}))
        process.stdin.close()
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                trust_env=False,
                timeout=2,
                headers={"origin": f"http://localhost:{port}"},
            ) as client:
                deadline = time.monotonic() + 30
                ready = False
                while time.monotonic() < deadline:
                    assert process.poll() is None, log_path.read_text()
                    try:
                        ready = client.get("/health/ready").status_code == 200
                    except httpx.HTTPError:
                        pass
                    if ready:
                        break
                    time.sleep(0.05)
                assert ready, log_path.read_text()
                assert (
                    client.post(
                        "/api/auth/login", json={"username": "native-user", "password": password}
                    ).status_code
                    == 200
                )
                response = client.post(
                    "/api/projects",
                    json={
                        "title": "Native Windows project",
                        "preferences": {"requirements": [{"category": "sofa"}], "variants": 1},
                    },
                )
                assert response.status_code == 201, response.text
                project_id = response.json()["id"]
                uploaded = client.post(
                    f"/api/projects/{project_id}/assets?kind=photo",
                    files={"file": ("room.png", png, "image/png")},
                )
                assert uploaded.status_code == 201, uploaded.text
        finally:
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == "win32" else signal.SIGINT)
            process.wait(timeout=20)
    assert password not in log_path.read_text()
