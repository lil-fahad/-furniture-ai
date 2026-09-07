"""Bounded archive access, provenance-preserving splits, and atomic dataset files."""

import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_member(info, maximum=600_000_000):
    path = PurePosixPath(info.filename)
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\\" in info.filename
        or ":" in info.filename
        or info.flag_bits & 1
        or stat.S_ISLNK(info.external_attr >> 16)
        or info.file_size > maximum
    ):
        raise ValueError(f"Unsafe or oversized archive member: {info.filename}")
    return path


def unique_members(archive):
    members = {}
    for info in archive.infolist():
        safe_member(info)
        if info.filename in members:
            raise ValueError("Duplicate archive member")
        members[info.filename] = info
    return members


def extract_member(archive, name, root, maximum=30_000_000):
    info = archive.getinfo(name)
    relative = safe_member(info, maximum)
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Extraction path escaped dataset root")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    with archive.open(info) as source, temporary.open("wb") as destination:
        shutil.copyfileobj(source, destination, 1024 * 1024)
    temporary.replace(path)
    return path


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(path)


def proposed_split(group, seed=42, validation_fraction=0.15, test_fraction=0.15):
    n = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:16], 16) / 2**64
    return (
        "test" if n < test_fraction else "validation" if n < test_fraction + validation_fraction else "train"
    )


def grouped_splits(rows):
    """Keep all identities and exact copies together; held-out membership wins."""
    parents = {}

    def find(value):
        parents.setdefault(value, value)
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parents[max(a, b)] = min(a, b)

    hashes = {}
    ids = set()
    for row in rows:
        if row["id"] in ids:
            raise ValueError("Duplicate dataset record ID")
        ids.add(row["id"])
        find(row["group_id"])
        sha = row.get("sha256") or row.get("content_sha256")
        if sha:
            if sha in hashes:
                union(row["group_id"], hashes[sha])
            hashes[sha] = row["group_id"]
    priority = {"train": 0, "validation": 1, "test": 2, "reserved": 3}
    assignment = {}
    for row in rows:
        group = find(row["group_id"])
        split = row["proposed_split"]
        assignment[group] = max(assignment.get(group, "train"), split, key=priority.__getitem__)
    output = {key: [] for key in priority}
    for row in sorted(rows, key=lambda r: r["id"]):
        group = find(row["group_id"])
        row["split_group"] = hashlib.sha256(group.encode()).hexdigest()[:24]
        row["split"] = assignment[group]
        output[row["split"]].append(row)
    return output


def source_array(archive, member, field):
    import ijson

    safe_member(archive.getinfo(member))
    with archive.open(member) as stream:
        yield from ijson.items(stream, field + ".item", use_float=True)


def download_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{12}\.jpg", value):
        raise ValueError("Unexpected COCO image filename")
    return value


def open_zip(path):
    archive = zipfile.ZipFile(path)
    try:
        unique_members(archive)
    except Exception:
        archive.close()
        raise
    return archive
