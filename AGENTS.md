# Agent Guide

## Project purpose

AI Execution Partner helps engineering teams identify priorities and delivery risks from Jira, GitHub, and (eventually) Teams activity. See `README.md` for the product goals. Treat planned connectors and alerts as future work unless they are present in the code; do not claim the agent has reviewed external data without a tool result.

## Repository layout

- `src/`: React 19 + TypeScript dashboard (Vite). Frontend tests are in `src/__tests__/`.
- `backend/`: independent Python project managed by uv. Code is in `backend/src/team_partner/` and tests are in `backend/tests/`.
- `backend/src/team_partner/app.py`: FastAPI routes, WebSocket conversation protocol, and application setup.
- `backend/src/team_partner/agents/`: Hyperforge agent runtime and SQLite-backed conversation/event/memory storage.
- `backend/src/team_partner/db.py`: SQLAlchemy tables and database setup; `settings.py`: environment configuration.
- `docker-compose.yaml`: frontend and backend services. `Dockerfile` builds the frontend; `backend/Dockerfile` builds the backend.

## Run and check

From the repository root:

```sh
npm ci
npm run dev               # Frontend: http://localhost:4200
npm run lint
npm test
npm run build
docker compose config --quiet
docker compose up --build  # Both services; frontend :4201, backend :8888 by default
```

From `backend/`:

```sh
uv sync --extra dev
uv run team-partner-http  # API docs: http://127.0.0.1:8888/docs
uv run --no-sync pytest tests/test_agent_api.py -q
uv run --no-sync ruff check src tests
uv run --no-sync ruff format --check src tests
```

Run targeted checks for the files changed. The backend has its own `pyproject.toml` and `uv.lock`; run uv commands from `backend/`, not the repository root.

## Backend conventions

- Keep HTTP/WebSocket handlers in `app.py` focused on request handling; keep agent construction in `agents/runtime.py` and persistence in `agents/storage.py` and `db.py`.
- Use the released Hyperforge dependency pinned in `backend/pyproject.toml` and its `hyperforge.harness_sdk` API. Pass new integrations as `HarnessTool` instances through `create_app(tools=...)` rather than coupling the API to a particular connector.
- SQLite is the current store. Conversation events must remain ordered and replayable after restart. Use `backend/tests/test_agent_api.py` as the existing end-to-end test pattern, with a stub model client instead of live model calls.
- There is currently **no authentication or user identity requirement**. Do not add required `user_id` parameters or auth dependencies to agent endpoints unless requested.
- The WebSocket at `/api/v1/agents/sessions/{session_id}/ws` replays events before accepting `prompt`, `steer`, `interrupt`, and `feedback_response` commands. Keep the existing event envelope and session lifecycle compatible when extending it.

## Configuration and containers

- Local backend settings come from environment variables or `backend/.env` (see `backend/.env.example`). The default SQLite URL is relative to the backend working directory.
- Docker Compose reads the optional repository-root `.env` (see `.env.example`) into the backend container. Compose sets `HTTP_HOST`, `HTTP_PORT`, and a SQLite URL under `/app/data`; the named `backend_data` volume persists the database.
- `NUA_API_KEY` is needed for real model-backed turns. Keep keys and local `.env`/SQLite files out of Git and Docker build contexts.
- Frontend host port is controlled by `FRONTEND_PORT` (default 4201); backend host port by `BACKEND_PORT` (default 8888).
