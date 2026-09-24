# Execution Partner

A lean React 19 + TypeScript workspace built with Vite. It includes ESLint, Prettier, Vitest, React Testing Library, and development/production container stages.

## Local development

```bash
npm ci
npm run dev
```

Open http://localhost:4200.

## Docker development

```bash
docker compose build
docker compose up -d
```

Open http://localhost:4201. Set `FRONTEND_PORT` to override the host port. The project is bind-mounted into `/app`, while container dependencies remain isolated in `/app/node_modules`.

## Docker backend

Copy `.env.example` to `.env` at the repository root and set `NUA_API_KEY` to enable agent prompts. Compose passes the variables in `.env` to the backend container; the backend binds to `0.0.0.0:8888` and stores SQLite data in the `backend_data` volume. `HTTP_HOST`, `HTTP_PORT`, and `DATABASE_URL` are set by Compose so the service remains reachable and its data persists.

```bash
docker compose up --build backend
```

Open http://localhost:8888/docs (or set `BACKEND_PORT` in `.env` to change the host port). Rebuild and start both services after code or image changes with:

```bash
docker compose up -d --build
```

The backend image includes `gh`. Set `GH_TOKEN` in the root `.env` to a fine-grained, read-only token scoped only to the repositories the assistant needs. Do not commit the token. To verify the GitHub integration, open the chatbot and enter this exact prompt:

```text
Use gh_cli with args ["pr","list","--repo","nuclia/data-platform","--limit","5","--json","number,title,state,author"]
```

The backend image includes the Atlassian CLI (`acli`) and mounts the host's
`~/.config/acli` directory by default. Set `ACLI_CONFIG_DIR` in the root `.env`
if the host configuration is elsewhere. ACLI OAuth secrets on macOS are stored
in Keychain and cannot be used by the Linux container, so authenticate an API
token profile in the shared directory when needed:

```bash
docker compose run --rm -T backend acli jira auth login \
  --site example.atlassian.net --email you@example.com --token < token.txt
docker compose exec backend acli jira auth status
```

Run the end-to-end WebSocket and ACLI smoke test from `backend/`:

```bash
uv run --no-sync python ../scripts/test-agent-websocket.py
uv run --no-sync python ../scripts/test-agent-websocket.py --require-authenticated
```

For local Python development and API details, see [backend/README.md](backend/README.md).

## Quality checks

```bash
npm run lint
npm test
npm run build
```

## Production image

```bash
docker build --target production -t execution-partner .
docker run --rm -p 8080:80 execution-partner
```

The Nginx stage supports client-side routing and exposes `/health`.
