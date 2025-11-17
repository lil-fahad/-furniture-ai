import subprocess
from pathlib import Path

REPOS = {
    "cubic5k": "https://github.com/CubiCasa/CubiCasa5k",
    "floorplancad": "https://github.com/lambdal/CAD-floorplan",
    "mlstructfp": "https://github.com/MLSTRUCT/MLSTRUCT-FP",
    "deepfloorplan": "https://github.com/zlzhaofeng/DeepFloorplan",
    "awesomeplans": "https://github.com/diegovalsesia/awesome-floorplans",
}


def clone_repo(name: str, url: str, target_root: Path) -> None:
    target = target_root / name
    if target.exists():
        print(f"[fetch] {name} already exists, skipping")
        return
    target_root.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(["git", "clone", "--depth", "1", url, str(target)])
    print(f"[fetch] cloned {name} -> {target}")


def fetch_all(root: Path = Path("datasets")) -> None:
    for name, url in REPOS.items():
        clone_repo(name, url, root)


if __name__ == "__main__":
    fetch_all()
