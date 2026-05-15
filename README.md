# Furniture AI System

End-to-end automation for blueprint analysis, furniture recommendation, and 3D
layout synthesis. The stack is a FastAPI backend, a Vite + React frontend, and
a set of Python automation scripts for datasets and training.

## Structure
- `backend/` — FastAPI app with `analyze`, `recommend`, and `layout3d` routes.
- `frontend/` — Vite + React client (Tailwind via CDN) for blueprint upload,
  detection, recommendations, and a 3D mesh viewer.
- `scripts/` — Automation for datasets, training, syncing, and cron orchestration.
- `models/` — Generated model artifacts and checkpoints (created at runtime).
- `datasets/` — Downloaded and processed datasets (created at runtime).

## Backend
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Endpoints:
- `GET /health` — service health.
- `POST /analyze/blueprint` — multipart upload, returns rooms + base64 preview.
- `POST /recommend/furniture` — JSON `{ "style": "modern", "budget": 1500 }`.
- `POST /layout3d/generate` — JSON `{ "blueprint_url": "..." }`.

## Frontend
```bash
npm install
npm run dev -- --host
```
Set `VITE_API_URL` to point at the backend when not on `http://localhost:8000`.

## Automation scripts
- `python scripts/datasets/fetch.py` — clone example datasets (requires network).
- `python scripts/datasets/preprocess.py` — normalize images and emit YOLO labels.
- `python scripts/datasets/build_furniture.py` — build the furniture catalog CSV.
- `python scripts/datasets/build_3d.py` — generate sample meshes.
- `python scripts/train/train_yolo.py` — write YOLO weights and report stubs.
- `python scripts/train/train_recommender.py` — train the recommender baseline.
- `python scripts/train/train_3d.py` — train the 3D layout stub.
- `python scripts/auto/update.py` — fetch and preprocess datasets.
- `python scripts/auto/train.py` — run scheduled training and snapshot checkpoints.
- `python scripts/auto/sync.py` — pull, commit, and push changes.
- `python scripts/cron/cron.py` — simple in-process scheduler for the above.
