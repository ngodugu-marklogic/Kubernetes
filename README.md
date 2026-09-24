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

The Atlassian CLI (`acli`) is not included in the backend image; install and authenticate it separately before using the `acli` tool. For local Python development and API details, see [backend/README.md](backend/README.md).

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
