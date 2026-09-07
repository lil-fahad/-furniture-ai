"""Exercise the shipped launch commands, including extraction into nested folders."""

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def invoke(root, *args, cwd=None):
    return subprocess.run(
        [sys.executable, str(root / "scripts/windows_train.py"), *map(str, args)],
        cwd=cwd or root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def annotations(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for split in ("train2017", "val2017"):
            archive.writestr(f"annotations/instances_{split}.json", "{}")
    return path


def test_package_check_works_without_install_from_unrelated_directory(tmp_path):
    result = invoke(ROOT, "--check-package", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["package_ok"] is True
    assert not (tmp_path / "data").exists()


def test_plan_finds_annotations_in_extraction_parent_without_installing(tmp_path):
    root = tmp_path / "Downloads" / "Furniture & AI" / "FurnitureAI-Windows"
    shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    archive = annotations(root.parent.parent / "annotations_trainval2017.zip")
    result = invoke(root, "--plan", "--task", "dino", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    plan = json.loads(result.stdout)
    assert plan["archive"] == str(archive.resolve())
    assert plan["dataset_root"] == str(root / "data" / "coco")
    assert not (root / "data").exists(), "Preview must not install or download anything"


def test_research_plan_uses_a_separate_coco_cache_and_forwards_research(tmp_path):
    archive = annotations(tmp_path / "annotations_trainval2017.zip")
    result = invoke(ROOT, "--plan", "--annotations", archive, "--research", "--data-root", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    plan = json.loads(result.stdout)
    assert plan["dataset_root"] == str(tmp_path / "coco-research")
    assert "--research" in plan["import_arguments"]


def test_explicit_archive_path_is_relative_to_callers_directory(tmp_path):
    archive = annotations(tmp_path / "input with spaces.zip")
    result = invoke(ROOT, "--plan", "--annotations", archive.name, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["archive"] == str(archive)


def test_wrong_zip_fails_before_any_install_or_data_creation(tmp_path):
    archive = tmp_path / "wrong.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("readme.txt", "No COCO instances here")
    result = invoke(ROOT, "--plan", "--annotations", archive, "--data-root", tmp_path / "data")
    assert result.returncode != 0
    assert "instances_train2017.json" in result.stderr
    assert not (tmp_path / "data").exists()


def test_missing_explicit_archive_does_not_silently_select_another(tmp_path):
    annotations(tmp_path / "annotations_trainval2017.zip")
    result = invoke(ROOT, "--plan", "--annotations", tmp_path / "missing.zip")
    assert result.returncode != 0
    assert "missing.zip" in result.stderr and "Archive not found" in result.stderr


def test_windows_distribution_has_no_extra_top_level_directory(tmp_path):
    output = tmp_path / "FurnitureAI-Windows-v2.zip"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_windows_package.py"), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "START-WINDOWS.cmd" in archive.namelist()
        assert "scripts/windows_launcher.py" in archive.namelist()
        assert not any(".venv" in name or name.startswith("data/") for name in archive.namelist())
        nested = tmp_path / "Furniture & AI" / "FurnitureAI-Windows"
        archive.extractall(nested)
    result = invoke(nested, "--check-package", cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    (nested / "scripts/windows_train.py").write_text("print('damaged')")
    result = subprocess.run(
        [sys.executable, str(nested / "scripts/windows_support.py"), "--check-package"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "windows_train.py" in result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows cmd.exe")
def test_cmd_launcher_passes_arguments_from_a_nested_path(tmp_path):
    root = tmp_path / "Furniture & AI" / "Nested folder"
    shutil.copytree(ROOT / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "START-WINDOWS.cmd", root)
    env = {**os.environ, "FURNITURE_NO_PAUSE": "1", "FURNITURE_PYTHON": sys.executable}
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(root / "START-WINDOWS.cmd"), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--doctor-only" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows UI test")
def test_native_panel_validates_a_selected_archive(tmp_path, monkeypatch):
    import tkinter as tk

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from windows_launcher import Launcher

    window = tk.Tk()
    panel = Launcher(window)
    panel.archive.set(str(annotations(tmp_path / "selected.zip")))
    panel.data_root.set(str(tmp_path / "data"))
    panel.start("plan")
    deadline = time.monotonic() + 20
    try:
        while panel.busy and time.monotonic() < deadline:
            window.update()
            time.sleep(0.02)
        assert not panel.busy
        assert "Completed" in panel.status.get()
        assert "selected.zip" in panel.output.get("1.0", "end")
        assert not (tmp_path / "data").exists()
    finally:
        if panel.busy:
            panel.stop()
        window.destroy()
