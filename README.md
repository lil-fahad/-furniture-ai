# Furniture AI System PRO — All-in-One Edition

This repository bundles a FastAPI backend, a lightweight AI engine mock, and a React frontend for experimenting with AI-assisted furniture design. The backend exposes routes to generate furniture previews and blueprints, while the AI engine mocks detection and recommendation endpoints.

## Project Layout
- `app/backend`: FastAPI backend with preview and blueprint routes.
- `app/ai_engine`: AI engine mock service with detection and recommendation endpoints.
- `app/frontend`: React client scaffolded for Vite.
- `app/infra/docker`: Docker Compose template to run the services together.

## Running Locally
1. Create a virtual environment and install backend dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r app/backend/requirements.txt
   ```
2. Launch the backend API:
   ```bash
   uvicorn app.backend.main:app --reload
   ```
3. Launch the AI engine (optional mock service):
   ```bash
   uvicorn app.ai_engine.main:app --reload --port 8001
   ```
4. For the frontend, install dependencies with `npm install` and start Vite via `npm run dev`.

## API Quickstart
- `GET /api/v1/health` — service health check.
- `POST /api/v1/furniture/preview` — generate preview instructions for a furniture concept.
- `POST /api/v1/blueprints` — build a simple blueprint outline given a name, style, and materials.

The mock AI engine provides `POST /detect` and `POST /recommend` endpoints for basic testing.
