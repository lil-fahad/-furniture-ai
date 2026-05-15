from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


TASKS = [
    {"name": "update", "interval": 60 * 60 * 24, "last": 0.0, "cmd": [PY, "scripts/auto/update.py"]},
    {"name": "train_weekly", "interval": 60 * 60 * 24 * 7, "last": 0.0, "cmd": [PY, "scripts/auto/train.py"]},
    {"name": "sync", "interval": 60 * 60, "last": 0.0, "cmd": [PY, "scripts/auto/sync.py"]},
]


def run_task(task: dict) -> None:
    print(f"[cron] running {task['name']}")
    subprocess.call(task["cmd"], cwd=ROOT)
    task["last"] = time.time()


def loop() -> None:
    while True:
        now = time.time()
        for task in TASKS:
            if now - task["last"] >= task["interval"]:
                run_task(task)
        time.sleep(60)


def main() -> None:
    loop()


if __name__ == "__main__":
    main()
