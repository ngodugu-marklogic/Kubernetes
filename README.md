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
docker compose up --build frontend
```

Open http://localhost:4201. Set `FRONTEND_PORT` to override the host port. The project is bind-mounted into `/app`, while container dependencies remain isolated in `/app/node_modules`.

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
