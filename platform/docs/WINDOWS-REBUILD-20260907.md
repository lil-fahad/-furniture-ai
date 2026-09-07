# Windows desktop rebuild

The previous distribution assumed the user was already inside the correct
extracted directory and had a working Python launcher. The native desktop path
now includes extraction, Python discovery, a bilingual control panel, data
selection, local application services, and supervised training.

## Components

- `INSTALL-FURNITURE.cmd` is generated beside the ZIP. It checks the ZIP's SHA-256
  and extracts it into a versioned per-user directory without overwriting an older
  installation. The checksum detects mismatches; it is not an independent publisher signature.
- `START-WINDOWS.cmd` finds Python 3.12 x64 and opens the panel. Explicit command
  arguments retain the training CLI. Paths are resolved relative to the script,
  not the shell working directory. Default GUI startup offers the packaged Python
  installation path when Python is absent.
- `windows_launcher.py` provides model/data selection, GPU diagnostics, setup,
  model downloads, studio startup, training, resume, cancellation and log access.
  Its event queue keeps subprocess output off the Tk thread and bounds displayed history.
- `windows_train.py` separates input validation from installation and training.
  The research flag is forwarded to COCO and uses a separate dataset cache.
- `desktop.py` initializes Alembic migrations and a local account, then supervises
  a loopback API, one SQLite worker, and one model service. Credentials travel on
  stdin, are hashed in the database, and are not printed in command lines or logs.
- `ml/service.py` adds an `all` role sharing a single execution lock across every
  model endpoint. Existing separate-role deployment remains available.
- `ml/runtime.py` adds Qwen inference through Transformers and clears failed model
  cache identity correctly. Structured output is validated against the project's
  two schemas; incomplete or invalid output is rejected.

The main application, geometric solver, dataset importers, model training,
evaluation, authentication, storage, tests and deployment code are included in the
distribution. The established model implementations remain in use; this release
does not claim to invent or retrain their pretrained weights.

## Verification

Run from `platform` with the documented dependencies installed:

```text
ruff check src tests migrations scripts
ruff format --check src tests migrations scripts
pytest -q
python scripts/windows_train.py --check-package
python scripts/build_windows_package.py --output dist/FurnitureAI-Windows-v2.zip
```

The native startup test launches an actual API subprocess, initializes the local
database, signs in, creates a project, uploads an image and shuts down the service.
Windows CI additionally runs CMD from a nested directory containing spaces and an
ampersand, and uses the actual Tk panel to select and validate an archive.

The archive test extracts into a nested directory, checks all inventory hashes,
then corrupts a file and requires verification to fail. Lock and subprocess tests
check mutual exclusion, saved error output and argument boundaries.

## Operational limits

The local SQLite mode is one desktop instance and one worker. Scalable deployment
uses the existing PostgreSQL/HTTPS architecture. Large GPU weights are downloaded
separately; successful CPU tests do not certify their quality, speed or VRAM fit.
The graphical training tasks cover DINO, SAM 2, SigLIP and layout. Other training
commands and required data contracts remain in `TRAINING.md`.

Qwen 7B requires substantial memory. SDXL CPU offload is enabled, but no arbitrary
GPU compatibility or time-to-completion guarantee is made. The user's Windows
device is not connected to this build environment. Suppliers remain deferred.
