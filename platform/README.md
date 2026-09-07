# Furniture AI

A room-design application with private projects, room-photo/floor-plan/PDF ingestion,
measured furniture layouts, SDXL proposals, model evaluation, consented preference
learning, and a durable PostgreSQL job queue. Supplier integration is deferred.
Furniture dimensions are editable concept specifications; there are no fabricated
SKUs, prices, stock levels, or purchase links.

**Windows GPU training with the uploaded COCO archive:**
[Arabic setup and one-file launcher](README-WINDOWS-AR.md).
[Measured data preparation and research training results](docs/DATA-EXECUTION-20260907.md).

## Delivery status

This directory contains executable application, inference, training, evaluation,
and deployment code. It does **not** contain trained custom weights, a licensed
training corpus, benchmark results from production GPUs, or a provisioned cloud.
Production acceptance requires the measurements and operational checks in
[EVALUATION.md](docs/EVALUATION.md) and [DEPLOYMENT.md](docs/DEPLOYMENT.md).
Training code improvements are not evidence that weights outperform a baseline.

The application never substitutes a synthetic answer when a model is unavailable.
Failed dependencies produce bounded retries and visible job errors. Tests replace
model HTTP calls explicitly; these fixtures are not reachable in the application.

## Model names

| Responsibility | Selected model | Implementation improvement |
|---|---|---|
| Open-vocabulary furniture detection | **Grounding DINO Base** | Domain supervised training, bounded boxes, class-aware NMS |
| Prompted segmentation | **SAM 2.1 Hiera Small** | Mask/prompt adaptation with BCE + Dice; protected door/window masks |
| Relative depth | **Depth Anything V2 Small** | Scale/shift-normalized inverse-depth loss + masked multiscale gradients |
| Floor-plan segmentation | **FurnitureFloorplanNet**; **HG-Furukawa Original on CubiCasa5K** for research | Licensed-data U-Net with room/icon CE + class-balanced Dice; isolated research adapter |
| Furniture arrangement | **FurnitureLayoutTransformer** | Room/keepout/access raster + furniture tokens; orientation and overlap losses; hard geometry checks |
| Rendering | **SDXL 1.0 + SDXL ControlNet Canny + SDXL ControlNet Depth + inpainting** | Domain LoRA/ControlNet training; edit-aware controls; exact unchanged pixels outside photo masks |
| Visual similarity | **SigLIP 2 Base Patch16-224** | Multi-positive identity-aware contrastive fine-tuning |
| Visual analyzer/evaluator | **Qwen2.5-VL-7B-Instruct** | Assistant-only LoRA supervision; schema-constrained private vLLM responses |
| Design preference ranking | **FurniturePreferenceRanker** | Pairwise supervised ranker with versioned seven-feature contract |

Pretrained models are pinned to immutable revisions in [models.lock.json](models.lock.json).
Model rationale, licensing, and exact Hub IDs: [MODELS.md](docs/MODELS.md).

## Run the application locally

Requires Python 3.12, Linux/macOS, and a current pip. Run from this directory:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements-test.lock
python -m pip install --no-deps -e .
alembic upgrade head
furniture create-user --username designer --tenant-name "Design studio"
uvicorn furniture_ai.api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open http://localhost:8000. Account creation prompts for a password; none is
embedded in the code. A second terminal starts `furniture worker`. Configure
model endpoints and install weights before requesting inference, as described
below. SQLite is supported for one local worker; production requires PostgreSQL.

## Run the complete inference stack

Requires Docker Compose with NVIDIA Container Toolkit and three independently
assigned CUDA devices for the supplied topology. Scoring runs on CPU. Device
count is a deployment choice, not a model requirement: external services can be
configured separately. Do not run all three GPU services on one device without
memory admission control. Budget VRAM from measured workloads, not these defaults.

```bash
python scripts/configure.py
python -m pip install -r requirements-ml.lock
python -m furniture_ai.ml.install --group all --output data/models
python -m furniture_ai.ml.install --group all --output data/models --verify
docker compose --profile inference build
docker compose --profile inference up -d
docker compose exec api furniture create-user --username designer --tenant-name "Design studio"
docker compose logs -f worker
```

`scripts/configure.py` exclusively creates a private `.env` with random credentials.
Model downloads can require substantial disk space and time. Review model terms
first. The supplied vLLM tag is a compatibility baseline; resolve and record an
image digest before production. No model downloads occur during serving.

To run only PostgreSQL/API/worker while using your own private model services:
set their fixed URLs in `.env`, then `docker compose up -d --build`.

Until licensed custom weights pass evaluation, floor plans use explicitly labelled
VLM observations, layouts use the implemented constraint solver, and ranking uses
documented fixed weights. Set the trained modes only after registering evaluated
checkpoints; missing weights cause an error rather than random-model inference.

## Use the application

1. Create an account using the administrative CLI and sign in.
2. Upload a JPEG, PNG, WebP, or floor-plan PDF; select the PDF page if needed.
3. Analyze the source. Review detected objects, masks, relative depth, observations,
   and uncertainties. Photo dimensions are never inferred as reliable metres.
4. Enter a rectangle or a polygon in metres. Include door swings/fixed areas and
   interior access points. Confirm measurements and furniture dimensions.
5. Generate up to four layouts, renderings, and evaluations. If automatic masks
   miss an editable region, upload a matching white-on-black PNG edit mask.
6. Inspect the measured plan, export JSON/CSV, or give an optional consented
   pairwise preference. Deleting a project revokes access immediately.

The measured plan is authoritative for placement. A photo rendering is a visual
interpretation: this system does not reconstruct a metrically calibrated 3D scene
from a single image or prove that every generated object matches its plan.

## Code organization

| Path | Responsibility |
|---|---|
| `src/furniture_ai/api.py`, `auth.py`, `middleware.py` | HTTP API, sessions, tenancy, rate limits, upload bounds, browser security |
| `models.py`, `jobs.py`, `worker.py` | Persistent state, leases, checkpoints, retries and cancellation |
| `storage.py`, `rasterize.py` | Private local/S3 objects, metadata stripping, bounded PDF rasterization |
| `layout.py`, `pipeline.py`, `providers.py` | Geometry, stage orchestration and typed model boundaries |
| `static/` | Same-origin responsive studio UI with no CDN dependencies |
| `ml/runtime.py`, `ml/service.py` | Actual model adapters and private admission-controlled inference endpoints |
| `ml/networks.py`, `ml/losses.py`, `ml/tasks.py` | Custom networks and foundation-model supervised objectives |
| `ml/data.py`, `ml/train.py`, `ml/train_vlm.py` | Rights validation, duplicate-safe splits, distributed training and resumable state |
| `ml/predict.py`, `ml/evaluate.py`, `ml/register.py` | Held-out inference, metric gates and digest-bound model promotion |
| `third_party/diffusers/` | Pinned upstream SDXL LoRA and ControlNet training implementations |
| `migrations/` | Explicit Alembic schema migration |
| `tests/` | Security, pipeline, geometry, ML and real-PostgreSQL concurrency tests |
| `deployment/`, `Dockerfile*`, `compose.yml` | Container deployment and production TLS gateway configuration |

## Training, evaluation and operations

* [Architecture and contracts](docs/ARCHITECTURE.md)
* [Models and provenance](docs/MODELS.md)
* [Data strategy and exact training commands](docs/TRAINING.md)
* [Evaluation and release gates](docs/EVALUATION.md)
* [Deployment, scaling, recovery and rollback](docs/DEPLOYMENT.md)
* [Security and retention](docs/SECURITY.md)
* [Verification evidence](docs/VERIFICATION.md)

```bash
ruff check src tests migrations scripts
ruff format --check src tests migrations scripts
pytest -q
# Real concurrency tests require a disposable PostgreSQL database:
TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/TEST_DB' pytest -q -m postgres
```

The repository's `furniture-platform.yml` workflow runs API tests, PostgreSQL
concurrency, migrations, a CPU ML test job, and the application container build.
# Windows desktop distribution (1.1)

Open `START-WINDOWS.cmd` to use the native control panel. It manages environment
setup, pinned model downloads, a local design studio, and real dataset training.
See [the Arabic Windows guide](README-WINDOWS-AR.md) or open `START-HERE.html`.
The local studio uses SQLite, one worker, and one serialized model service, including
Qwen through Transformers; Docker and vLLM are not required for this local path.
It binds only to loopback. Production deployment still uses the PostgreSQL and
HTTPS configuration below. Model weights and large datasets download separately.
