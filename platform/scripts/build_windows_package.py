"""Build a flat Windows ZIP, excluding data, environments and private configuration."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"src", "scripts", "docs", "tests", "examples", "migrations", "deployment", "third_party"}
TOP_LEVEL = {
    "START-WINDOWS.cmd",
    "INSTALL-PYTHON.cmd",
    "README-WINDOWS-AR.md",
    "README.md",
    "START-HERE.html",
    "pyproject.toml",
    "models.lock.json",
    "alembic.ini",
    "compose.yml",
    "Dockerfile",
    "Dockerfile.model",
    ".dockerignore",
    ".gitignore",
    "package.json",
    "package-lock.json",
}


def build(output):
    output = Path(output).resolve()
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", output.name):
        raise ValueError("Use a ZIP filename containing only letters, digits, dots, underscores and hyphens")
    entries = {}
    candidates = [path for path in ROOT.iterdir() if path.is_file()]
    for directory in sorted(DIRECTORIES):
        if (ROOT / directory).is_dir():
            candidates.extend((ROOT / directory).rglob("*"))
    for path in sorted(candidates):
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink():
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            if relative.as_posix() not in {".dockerignore", ".gitignore"}:
                continue
        if path.suffix in {".pyc", ".zip", ".log", ".tmp", ".part"}:
            continue
        if relative.parts[0] not in DIRECTORIES and relative.as_posix() not in TOP_LEVEL:
            if len(relative.parts) != 1 or not path.name.startswith("requirements"):
                continue
        data = path.read_bytes()
        if path.suffix == ".cmd":
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        entries[relative.as_posix()] = data
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}
    entries["package-manifest.json"] = json.dumps(
        {"format_version": 1, "sha256": hashes}, sort_keys=True, indent=2
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".zip.part")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 9, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    temporary.replace(output)
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    template = (ROOT / "scripts/install_windows.cmd.template").read_text(encoding="utf-8")
    installer = (
        template.replace("@ARCHIVE_NAME@", output.name)
        .replace("@ARCHIVE_SHA@", sha)
        .replace("@SHORT_SHA@", sha[:12])
    )
    installer_path = output.parent / "INSTALL-FURNITURE.cmd"
    installer_path.write_bytes(installer.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    return {
        "path": str(output),
        "installer": str(installer_path),
        "files": len(entries),
        "bytes": output.stat().st_size,
        "sha256": sha,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(parser.parse_args().output), indent=2))
