"""Start the local project or install all pinned inference models from the desktop panel."""

import argparse
import json
import os
import signal
import subprocess
import sys

from windows_support import ROOT, Runner, SessionLock, check_package, stop_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--models", action="store_true")
    group.add_argument("--studio", action="store_true")
    args = parser.parse_args()
    check_package()
    python = ROOT / ".venv-win/Scripts/python.exe"
    if not python.is_file():
        raise ValueError("Use Setup to install the Windows environment first.")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    with SessionLock(ROOT / "logs/operation.lock"):
        runner = Runner(ROOT, env)
        try:
            if args.models:
                runner.run(
                    [python, "-m", "furniture_ai.ml.install", "--group", "all"], "Download studio models"
                )
                runner.run(
                    [python, "-m", "furniture_ai.ml.install", "--group", "all", "--verify"],
                    "Verify studio models",
                )
            else:
                credentials = sys.stdin.read(8193)
                record = json.loads(credentials)
                if not isinstance(record.get("username"), str) or not isinstance(record.get("password"), str):
                    raise ValueError("Local username and password are required")
                record.clear()
                runner.run(
                    [python, "-m", "furniture_ai.ml.gpu_doctor", "--output", ROOT / "data/gpu-report.json"],
                    "Check studio GPU",
                )
                # Credentials go over stdin, never in process arguments, environment or logs.
                runner.state["stage"] = "Run local studio"
                runner.finish("running")
                with runner.log_path.open("a", encoding="utf-8") as log:
                    flags = (
                        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                        if sys.platform == "win32"
                        else {"start_new_session": True}
                    )
                    with subprocess.Popen(
                        [python, "-m", "furniture_ai.desktop", "--credentials-stdin"],
                        cwd=ROOT,
                        env=env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        **flags,
                    ) as child:
                        try:
                            child.stdin.write(credentials)
                            child.stdin.close()
                            credentials = ""
                            for line in child.stdout:
                                log.write(line)
                                log.flush()
                                print(line, end="", flush=True)
                            if child.wait() not in (0, 130):
                                raise RuntimeError(f"Studio failed. Details: {runner.log_path}")
                        except BaseException:
                            stop_process(child)
                            raise
            runner.finish("completed")
        except KeyboardInterrupt:
            runner.finish("cancelled")
            return 130
        except Exception as error:
            runner.finish("failed", str(error))
            raise
    return 0


if __name__ == "__main__":

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupt)
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Furniture AI stopped: {error}", file=sys.stderr)
        sys.exit(1)
