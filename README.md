# Furniture AI System PRO — All-in-One Edition

A starter codebase for an AI-assisted furniture design platform. The repository includes:

- A FastAPI backend with sample routes for furniture inventory and blueprint previews.
- A minimal React frontend scaffold.
- AI engine placeholders for model training and inference.
- Utility scripts to speed up local iteration with OpenAI models.

## Backend quickstart

```bash
uvicorn app.backend.main:app --reload
```

Available sample endpoints:
- `GET /v1/health` – readiness probe
- `GET /v1/furniture` – list available furniture catalog items
- `GET /v1/furniture/{item_id}` – fetch a single catalog item
- `GET /v1/blueprints` – preview blueprint ideas that reference furniture items

## AI helper utilities

`tools/codex_auto_dev.py` exposes a helper class that can auto-fix, refactor, rewrite, or generate files using the OpenAI API. Set `OPENAI_API_KEY` in your environment before using it.

## Repository layout

- `app/backend` — FastAPI services, utilities, and sample data models.
- `app/frontend` — React application scaffold.
- `app/ai_engine` — placeholders for training and inference scripts.
- `app/infra` — Docker and deployment assets.
