"""Standard-library path discovery, integrity checks and process supervision."""

import argparse
import datetime
import hashlib
import json
import os
import signal
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "START-WINDOWS.cmd",
    "scripts/windows_train.py",
    "scripts/windows_launcher.py",
    "scripts/windows_support.py",
    "src/furniture_ai/ml/train.py",
    "src/furniture_ai/ml/gpu_doctor.py",
    "models.lock.json",
    "requirements-windows-base.lock",
    "requirements-windows-ml.lock",
    "pyproject.toml",
)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def check_package(root=ROOT):
    root = Path(root).resolve()
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise ValueError("Extract the complete ZIP first. Missing files: " + ", ".join(missing))
    manifest, verified = root / "package-manifest.json", 0
    if manifest.is_file():
        entries = json.loads(manifest.read_text(encoding="utf-8"))["sha256"]
        if not set(REQUIRED).issubset(entries):
            raise ValueError("Incomplete package manifest")
        for name, expected in entries.items():
            relative = PurePosixPath(name)
            target = (root / relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(root):
                raise ValueError("Invalid package path")
            if not target.is_file():
                raise ValueError(f"Package file missing: {name}")
            with target.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise ValueError(f"Package file changed or damaged: {name}. Extract a fresh copy.")
            verified += 1
    return {"package_ok": True, "root": str(root), "files_verified": verified}


def downloads_directory():
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
                return Path(os.path.expandvars(value))
        except OSError:
            pass
    return Path.home() / "Downloads"


def locate_archive(explicit, filename, data_root, root=ROOT):
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if not candidate.is_file():
            raise ValueError(f"Archive not found: {candidate}")
        return candidate
    folders = [Path(data_root) / "input", root, root.parent, root.parent.parent, downloads_directory()]
    for folder in dict.fromkeys(folders):
        candidate = folder / filename
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError(f"Archive not found: {filename}. Use Browse in the launcher to select the ZIP.")


def validate_archive(path, task):
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {
                "dino": {"annotations/instances_train2017.json", "annotations/instances_val2017.json"},
                "sam2": {"annotations/instances_train2017.json", "annotations/instances_val2017.json"},
                "siglip": {"furniture_products.jsonl", "image_index.jsonl", "LICENSE-CC-BY-4.0.txt"},
            }.get(task, set())
            if required - names:
                raise ValueError("Wrong dataset ZIP. Missing: " + ", ".join(sorted(required - names)))
            if not names:
                raise ValueError("Dataset ZIP is empty")
    except zipfile.BadZipFile as error:
        raise ValueError(f"Invalid ZIP: {path}") from error


class SessionLock:
    """An OS lock released even on crashes; the marker file is not a busy flag."""

    def __init__(self, path):
        self.path, self.stream = Path(path), None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.stream.close()
            self.stream = None
            raise ValueError("Another Furniture AI operation is running in this folder.") from error
        return self

    def __exit__(self, *exc):
        if self.stream is not None:
            self.stream.close()


def stop_process(process):
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


class Runner:
    def __init__(self, root, env):
        self.root, self.env = Path(root), env
        stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        self.log_path = self.root / "logs" / f"session-{stamp}-{uuid.uuid4().hex[:8]}.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state = {"status": "running", "stage": "startup", "log": str(self.log_path)}
        self.report_path = self.root / "logs" / "latest-session.json"
        self.finish("running")

    def finish(self, status, error=None):
        self.state.update(status=status, error=error)
        write_json(self.report_path, self.state)

    def run(self, arguments, stage, acceptable=(0,)):
        command = list(map(str, arguments))
        self.state["stage"] = stage
        self.finish("running")
        print(f"\n[{stage}]\nRunning: {subprocess.list2cmdline(command)}", flush=True)
        flags = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if sys.platform == "win32"
            else {"start_new_session": True}
        )
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{stage}]\n{subprocess.list2cmdline(command)}\n")
            log.flush()
            with subprocess.Popen(
                command,
                cwd=self.root,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **flags,
            ) as child:
                try:
                    for line in child.stdout:
                        log.write(line)
                        log.flush()
                        print(line, end="", flush=True)
                    code = child.wait()
                except BaseException:
                    stop_process(child)
                    raise
        if code not in acceptable:
            raise RuntimeError(f"{stage} failed (exit {code}). Details: {self.log_path}")
        return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-package", action="store_true", required=True)
    parser.parse_args()
    try:
        print(json.dumps(check_package()))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
