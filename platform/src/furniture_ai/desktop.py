"""Local Windows studio: migrated SQLite, private accounts, one worker and one model host."""

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from furniture_ai.auth import check_password
from furniture_ai.cli import create_user
from furniture_ai.config import Settings
from furniture_ai.db import make_engine, sessions
from furniture_ai.models import User

ROOT = Path(__file__).resolve().parents[2]


def initialize_desktop(data_root, username, password, port=8765, model_port=8766):
    username = username.strip().lower()
    if not 3 <= len(username) <= 120 or not 12 <= len(password) <= 256:
        raise ValueError("Username requires 3-120 characters and password requires 12-256 characters")
    if not (1024 <= port <= 65535 and 1024 <= model_port <= 65535) or port == model_port:
        raise ValueError("Choose two distinct unprivileged local ports")
    data_root = Path(data_root).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    config_path = data_root / "desktop-config.json"
    if not config_path.exists():
        private = {
            "version": 1,
            "model_key": secrets.token_urlsafe(48),
            "metrics_key": secrets.token_urlsafe(48),
        }
        try:
            fd = os.open(config_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                json.dump(private, output)
    private = json.loads(config_path.read_text(encoding="utf-8"))
    if private.get("version") != 1 or len(private.get("model_key", "")) < 32:
        raise ValueError("Invalid local configuration; restore desktop-config.json from your backup")
    provider = f"http://127.0.0.1:{model_port}"
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url=f"sqlite:///{(data_root / 'studio.db').as_posix()}",
        public_origin=f"http://localhost:{port}",
        allowed_hosts=["localhost", "127.0.0.1"],
        storage_backend="local",
        data_dir=data_root / "objects",
        vision_url=provider + "/v1",
        vision_model="Qwen/Qwen2.5-VL-7B-Instruct",
        vision_revision=json.loads((ROOT / "models.lock.json").read_text())["models"]["evaluator"][
            "revision"
        ],
        vision_api_key=private["model_key"],
        model_api_key=private["model_key"],
        metrics_token=private["metrics_key"],
        perception_url=provider,
        generation_url=provider,
        scoring_url=provider,
        provider_timeout=300,
        generation_timeout=900,
        layout_mode="constraints",
        ranking_mode="weighted",
    )
    migration = Config(str(ROOT / "alembic.ini"))
    migration.set_main_option("script_location", str(ROOT / "migrations"))
    migration.attributes["settings"] = settings
    command.upgrade(migration, "head")
    engine = make_engine(settings.database_url)
    factory = sessions(engine)
    try:
        with factory() as db:
            user = db.scalar(select(User).where(User.username == username))
            if user and (not user.active or not check_password(user.password_hash, password)):
                raise ValueError("Incorrect password for the existing local account")
        if user is None:
            create_user(factory, username, password, tenant_name="Local design studio")
    finally:
        engine.dispose()
    env = {}
    for name in type(settings).model_fields:
        value = getattr(settings, name)
        if value is None:
            continue
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        elif isinstance(value, (list, dict)):
            value = json.dumps(value)
        env["FURNITURE_" + name.upper()] = str(value)
    env.update(
        FURNITURE_ML_ROLE="all",
        FURNITURE_ML_API_KEY=private["model_key"],
        FURNITURE_ML_MODELS_DIR=str(ROOT / "data/models"),
        FURNITURE_ML_LOCK_PATH=str(ROOT / "models.lock.json"),
        FURNITURE_ML_CPU_OFFLOAD="true",
        FURNITURE_ML_FLOORPLAN_BACKEND="vlm",
        PYTHONUTF8="1",
        PYTHONUNBUFFERED="1",
        PYTHONPATH=str(ROOT / "src"),
    )
    return settings, env


def wait_for_service(url, processes, timeout=120):
    deadline = time.monotonic() + timeout
    opener = build_opener(ProxyHandler({}))
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("A studio service exited. Read the session log.")
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError):
            pass
        threading.Event().wait(0.2)
    raise RuntimeError("Studio startup timed out. Read the session log.")


def serve(env, port, model_port, *, api_only=False, open_browser=True):
    ports = [port] if api_only else [port, model_port]
    for number in ports:
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", number))
            except OSError as error:
                raise ValueError(
                    f"Port {number} is already in use. Stop the other local studio first."
                ) from error
    processes = []
    try:
        commands = [
            [
                sys.executable,
                "-m",
                "uvicorn",
                "furniture_ai.api:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ]
        ]
        if not api_only:
            commands.append(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "furniture_ai.ml.service:create_model_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(model_port),
                ]
            )
        for arguments in commands:
            processes.append(subprocess.Popen(arguments, cwd=ROOT, env={**os.environ, **env}))
        wait_for_service(f"http://127.0.0.1:{port}/health/ready", processes)
        if not api_only:
            wait_for_service(f"http://127.0.0.1:{model_port}/health/ready", processes)
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "furniture_ai.worker"], cwd=ROOT, env={**os.environ, **env}
                )
            )
        url = f"http://localhost:{port}"
        print(f"STUDIO_READY {url}", flush=True)
        if api_only:
            print("API-only mode: projects and uploads work; AI jobs require the full studio.", flush=True)
        if open_browser:
            webbrowser.open(url)
        while all(process.poll() is None for process in processes):
            threading.Event().wait(0.5)
        raise RuntimeError("A studio process stopped unexpectedly. See the session log.")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/desktop")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model-port", type=int, default=8766)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--credentials-stdin", action="store_true", required=True)
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    credentials = json.loads(sys.stdin.read(8193))
    _, env = initialize_desktop(
        args.data_root, credentials["username"], credentials["password"], args.port, args.model_port
    )
    credentials.clear()
    env["FURNITURE_ML_DEVICE"] = args.device
    if not args.api_only:
        from furniture_ai.ml.config import ModelSettings

        settings = ModelSettings(
            _env_file=None, models_dir=ROOT / "data/models", lock_path=ROOT / "models.lock.json"
        )
        for alias in json.loads(settings.lock_path.read_text())["models"]:
            try:
                settings.model_path(alias)
            except (OSError, ValueError, KeyError) as error:
                raise ValueError(
                    f"Model {alias} is missing or invalid. Use Download models before Open studio."
                ) from error
    serve(env, args.port, args.model_port, api_only=args.api_only, open_browser=not args.no_browser)


if __name__ == "__main__":

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupt)
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"Studio stopped: {error}", file=sys.stderr)
        sys.exit(1)
