"""Local CUDA diagnostics without telemetry, driver installation, or system changes."""

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from furniture_ai.ml.dataset_io import write_json


def inspect_gpu():
    report = {
        "os": platform.system(),
        "python": platform.python_version(),
        "cuda_available": False,
        "driver_inventory": [],
        "devices": [],
        "kernel_check": False,
        "errors": [],
    }
    executable = shutil.which("nvidia-smi")
    if executable:
        try:
            result = subprocess.run(
                [
                    executable,
                    "--query-gpu=name,driver_version,memory.total,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if result.returncode == 0:
                report["driver_inventory"] = result.stdout.strip().splitlines()
            else:
                report["errors"].append("nvidia-smi inventory failed: " + result.stderr.strip())
        except (OSError, subprocess.SubprocessError) as error:
            report["errors"].append("nvidia-smi inventory failed: " + str(error))
    try:
        import torch

        report.update(
            torch=torch.__version__,
            compiled_cuda=torch.version.cuda,
            cuda_available=torch.cuda.is_available(),
        )
        if not torch.cuda.is_available():
            report["errors"].append(
                "This Python environment cannot access CUDA. Check NVIDIA GPU/driver and the installed PyTorch CUDA wheel."
            )
            return report
        for index in range(torch.cuda.device_count()):
            device = torch.cuda.get_device_properties(index)
            with torch.cuda.device(index):
                free, total = torch.cuda.mem_get_info()
                # Exercise both the actual forward and backward CUDA kernels.
                x = torch.randn(128, 128, device=f"cuda:{index}", requires_grad=True)
                (x @ x.T).square().mean().backward()
                torch.cuda.synchronize()
                if not torch.isfinite(x.grad).all():
                    raise RuntimeError("CUDA kernel test produced nonfinite gradients")
                report["devices"].append(
                    {
                        "index": index,
                        "name": device.name,
                        "compute_capability": [device.major, device.minor],
                        "total_bytes": total,
                        "free_bytes": free,
                        "bf16_supported": torch.cuda.is_bf16_supported(),
                    }
                )
                del x
        report["kernel_check"] = True
    except (ImportError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        report["errors"].append(str(error))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("gpu-report.json"))
    args = parser.parse_args()
    report = inspect_gpu()
    write_json(args.output, report)
    print(json.dumps(report, indent=2), flush=True)
    if not report["kernel_check"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
