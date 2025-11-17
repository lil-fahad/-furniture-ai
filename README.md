# Furniture AI System PRO — All-in-One Edition

A structured starter kit for experimenting with AI-powered furniture design workflows. The project now ships with organized backend, AI engine, frontend, and infrastructure folders to make local development straightforward.

## Repository layout
- `app/backend/` — FastAPI application exposing REST endpoints and simple services for blueprints and furniture assets.
- `app/ai_engine/` — FastAPI microservice stubs for detection and recommendations.
- `app/frontend/` — React/Vite frontend placeholder.
- `app/infra/docker/` — Example Docker Compose definition wiring the services together.

## Getting started

### Backend
```bash
cd app/backend
uvicorn app.backend.main:app --reload
```

### AI Engine
```bash
cd app/ai_engine
uvicorn app.ai_engine.main:app --reload --port 8001
```

### Frontend
```bash
cd app/frontend
npm install
npm run dev
```

### Docker Compose
```bash
cd app/infra/docker
docker compose up --build
```

## Notes
- Logging is configured centrally via `app/backend/utils/logger.py` for backend components.
- Auth helpers in `app/backend/auth/jwt.py` provide a lightweight token contract suitable for local testing.
