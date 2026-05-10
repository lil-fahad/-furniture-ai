from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    print(f"[auto:update] running {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    run(["python3", "scripts/datasets/fetch.py"])
    run(["python3", "scripts/datasets/preprocess.py"])
    run(["python3", "scripts/datasets/build_furniture.py"])
    run(["python3", "scripts/datasets/build_3d.py"])


if __name__ == "__main__":
    main()
