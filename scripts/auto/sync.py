import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> str:
    print(f"[auto:sync] running {' '.join(cmd)}")
    return subprocess.check_output(cmd, cwd=ROOT).decode().strip()


def main() -> None:
    run(["git", "pull", "--rebase", "--autostash"])
    run(["git", "add", "-A"])
    try:
        run(["git", "commit", "-m", "Automated sync"]) 
    except subprocess.CalledProcessError:
        print("[auto:sync] nothing to commit")
    run(["git", "push"])


if __name__ == "__main__":
    main()
