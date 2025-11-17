from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlparse


class PipelineError(Exception):
    """Custom exception for pipeline failures."""


@dataclass
class CommandResult:
    stdout: str
    stderr: str


class FullAIPipeline:
    """A safer variant of the experimental end-to-end AI pipeline.

    This version avoids executing generated code or shell strings directly and
    confines filesystem access to locations inside the repository.
    """

    def __init__(self, base: str | Path | None = None, datasets_subdir: str = "datasets"):
        self.base = Path(base) if base else Path(__file__).resolve().parents[1]
        self.base = self.base.resolve()
        self.datasets = (self.base / datasets_subdir).resolve()
        self.datasets.mkdir(parents=True, exist_ok=True)

    def _run_command(self, args: Sequence[str], *, cwd: Path | None = None, timeout: int = 300) -> CommandResult:
        if not args:
            raise PipelineError("No command provided")
        cwd = cwd or self.base
        completed = subprocess.run(args, check=True, capture_output=True, text=True, cwd=str(cwd), timeout=timeout)
        return CommandResult(stdout=completed.stdout, stderr=completed.stderr)

    def _validate_repo_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise PipelineError("Only HTTPS git URLs are allowed")
        if parsed.netloc not in {"github.com", "www.github.com"}:
            raise PipelineError("Repository host is not allowed")
        if not parsed.path or "." in parsed.path.split("/")[-1]:
            raise PipelineError("Repository path looks invalid")

    def _safe_dataset_folder(self, name: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise PipelineError("Dataset folder contains illegal characters")
        target = (self.datasets / name).resolve()
        if self.base not in target.parents:
            raise PipelineError("Dataset folder escapes repository boundary")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _ensure_within_base(self, path: str | Path, *, allow_nonexistent: bool = False) -> Path:
        resolved = (self.base / path).resolve()
        if self.base not in resolved.parents and resolved != self.base:
            raise PipelineError("Path escapes repository boundary")
        if not allow_nonexistent and not resolved.exists():
            raise PipelineError(f"Path does not exist: {resolved}")
        return resolved

    def fetch_repos(self, repos: Mapping[str, str]) -> dict[str, dict[str, str]]:
        results: dict[str, dict[str, str]] = {}
        for name, url in repos.items():
            target = self._safe_dataset_folder(name)
            self._validate_repo_url(url)
            if target.exists() and any(target.iterdir()):
                results[name] = {"status": "exists", "path": str(target)}
                continue
            clone_args = ["git", "clone", "--depth", "1", url, str(target)]
            command_result = self._run_command(clone_args)
            results[name] = {"status": "cloned", "path": str(target), "stdout": command_result.stdout}
        return results

    def transform(self, folder: str, instruction: str, script_path: str | Path | None = None) -> Path:
        target_dir = self._safe_dataset_folder(folder)
        plan_file = target_dir / "TRANSFORM_PLAN.txt"
        plan_file.write_text(
            "\n".join(
                [
                    "Transformation instructions recorded for manual review.",
                    f"Target dataset: {target_dir}",
                    f"Instruction: {instruction}",
                ]
            )
        )
        if script_path:
            script = self._ensure_within_base(script_path)
            self._run_command(["python3", str(script), str(target_dir), instruction])
        return plan_file

    def train_yolo(self, yaml_path: str | Path, epochs: int = 50) -> CommandResult:
        config = self._ensure_within_base(yaml_path)
        return self._run_command(["yolo", "detect", "train", f"data={config}", f"epochs={epochs}", "imgsz=640"])

    def train_recommender(self, csv_path: str | Path, model_out: str | Path, script_path: str | Path) -> CommandResult:
        data_csv = self._ensure_within_base(csv_path)
        model_path = self._ensure_within_base(model_out, allow_nonexistent=True)
        script = self._ensure_within_base(script_path)
        return self._run_command(["python3", str(script), str(data_csv), str(model_path)])

    def run_full_pipeline(self) -> None:
        repos = {
            "cubic5k": "https://github.com/CubiCasa/CubiCasa5k",
            "floorplancad": "https://github.com/lambdal/CAD-floorplan",
            "mlstructfp": "https://github.com/MLSTRUCT/MLSTRUCT-FP",
            "deepfloorplan": "https://github.com/zlzhaofeng/DeepFloorplan",
            "awesomeplans": "https://github.com/diegovalsesia/awesome-floorplans",
            "front_tools": "https://github.com/3D-FRONT-Official/3D-FRONT-tools",
            "interior_tools": "https://github.com/xiaochenchenhh/InteriorNet-tools",
        }

        self.fetch_repos(repos)
        self.transform("cubic5k", "Convert all floorplans into PNG + YOLO labels in datasets/yolo/cubic5k")
        self.transform("floorplancad", "Convert all CAD/ SVG files into PNG + JSON for rooms")
        self.transform("mlstructfp", "Convert all MLSTRUCT annotations to YOLO class labels")
        self.transform("front_tools", "Extract 3D room structure + furniture placement into JSON")
        self.transform("interior_tools", "Extract 3D room meshes into datasets/3d")
        self.transform("awesomeplans", "Generate furniture dataset CSV including size, style, material")

        # Training steps require explicit, vetted scripts provided by the caller.
        # self.train_yolo("datasets/cubic5k/yolo/data.yaml", epochs=80)
        # self.train_recommender("datasets/awesomeplans/furniture.csv", "models/recommender.pth", script_path)


__all__ = ["FullAIPipeline", "PipelineError", "CommandResult"]
