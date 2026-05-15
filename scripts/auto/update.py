from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    print(f"[auto:update] running {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    py = sys.executable
    run([py, "scripts/datasets/fetch.py"])
    run([py, "scripts/datasets/preprocess.py"])
    run([py, "scripts/datasets/build_furniture.py"])
    run([py, "scripts/datasets/build_3d.py"])


if __name__ == "__main__":
    main()
