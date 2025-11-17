from pathlib import Path
import subprocess
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DIR = ROOT / "models" / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str]) -> None:
    print(f"[auto:train] running {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=ROOT)


def checkpoint(name: str) -> None:
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dest = CHECKPOINT_DIR / f"{name}-{stamp}.txt"
    dest.write_text(f"checkpoint {name} {stamp}\n")
    print(f"[auto:train] wrote checkpoint {dest}")


def train_recommender_daily() -> None:
    run(["python", "scripts/train/train_recommender.py"])
    checkpoint("recommender")


def train_yolo_weekly() -> None:
    run(["python", "scripts/train/train_yolo.py"])
    checkpoint("yolo")


def main() -> None:
    train_recommender_daily()
    train_yolo_weekly()
    run(["python", "scripts/train/train_3d.py"])


if __name__ == "__main__":
    main()
