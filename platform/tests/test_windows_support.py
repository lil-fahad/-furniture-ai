import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/windows_support.py"
spec = importlib.util.spec_from_file_location("windows_support_test", SCRIPT)
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


def test_runner_keeps_failure_output_and_argument_boundaries(tmp_path):
    runner = support.Runner(tmp_path, {**os.environ, "PYTHONUTF8": "1"})
    with pytest.raises(RuntimeError, match="exit 7"):
        runner.run(
            [sys.executable, "-c", "import sys; print(sys.argv[1]); sys.exit(7)", "a & b / أثاث"], "fixture"
        )
    assert "a & b / أثاث" in runner.log_path.read_text(encoding="utf-8")
    runner.finish("failed", "exit 7")
    report = json.loads(runner.report_path.read_text())
    assert report["status"] == "failed" and report["stage"] == "fixture"


def test_lock_blocks_a_second_process_then_releases(tmp_path):
    lock = tmp_path / "operation.lock"
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1]); from windows_support import SessionLock; "
        "session = SessionLock(sys.argv[2]); session.__enter__(); session.__exit__()"
    )

    def attempt():
        return subprocess.run(
            [sys.executable, "-c", probe, str(SCRIPT.parent), str(lock)],
            capture_output=True,
            text=True,
            timeout=10,
        )

    with support.SessionLock(lock):
        assert attempt().returncode != 0
    assert attempt().returncode == 0
