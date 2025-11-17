# Furniture AI System

End-to-end automation for blueprint analysis, furniture recommendation, and 3D layout synthesis. The stack includes FastAPI services, automation scripts for datasets and training, and a Vite React frontend.

## Structure
- `backend/` — FastAPI app with analysis, recommendation, and 3D layout routes.
- `frontend/` — Vite React client with blueprint upload, detection, recommendations, and 3D viewer pages.
- `scripts/` — Automation for datasets, training, syncing, and cron orchestration.
- `models/` — Trained model artifacts and checkpoints.
- `datasets/` — Downloaded and processed datasets.

## Backend
Install dependencies and run locally:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Frontend
Install dependencies and start the Vite dev server:
```bash
npm install
npm run dev -- --host
```

## Automation
- `python scripts/datasets/fetch.py` — clone example datasets.
- `python scripts/datasets/preprocess.py` — normalize images and create YOLO labels.
- `python scripts/datasets/build_furniture.py` — build furniture catalog CSV.
- `python scripts/datasets/build_3d.py` — generate sample meshes.
- `python scripts/train/train_yolo.py` — create YOLO weights and report placeholders.
- `python scripts/train/train_recommender.py` — train recommender baseline.
- `python scripts/train/train_3d.py` — train 3D layout stub.
- `python scripts/auto/update.py` — fetch and preprocess datasets.
- `python scripts/auto/train.py` — run scheduled training and checkpoints.
- `python scripts/auto/sync.py` — pull, commit, and push changes.
- `python scripts/cron/cron.py` — simple scheduler for update/train/sync.
