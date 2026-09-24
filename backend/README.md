# AI Team Partner

Python backend for an AI team partner and scrum master. The FastAPI service exposes
resumable Hyperforge agent conversations and stores conversation history, memories,
and shared team scope in a local SQLite database. Agent tools manage team members
(name, Jira account ID, GitHub login, ownership), Jira agile boards (board ID, name,
optional project key and site URL), and GitHub repositories (owner/repo). The agent
can run the host's `gh` and `acli` commands to investigate that saved scope.

## Getting started

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

Hyperforge comes from the [`execution-partner` branch](https://github.com/nuclia/hyperforge/tree/execution-partner)
of `nuclia/hyperforge`. The exact commit is pinned in `pyproject.toml` and
`uv.lock`; `uv sync --locked` (including in the backend Docker image) installs
that commit. When customizing Hyperforge, push changes to that branch, update
the `rev` in `pyproject.toml`, and run `uv lock` from this directory.

```sh
cd backend
uv sync --extra dev
cp .env.example .env
# Set NUA_API_KEY in .env to enable model-backed prompts.
uv run team-partner-http
```

The API is available at `http://127.0.0.1:8888/docs`. Configuration uses
environment variables (or `ENV_FILE` to select an env file): `HTTP_HOST`,
`HTTP_PORT`, `DEBUG`, `DATABASE_URL` (SQLite URL, default
`sqlite:///./team_partner.db`), `NUA_API_KEY`, `NUA_API_URI`, and
`DEFAULT_CHAT_MODEL`. The SQLite schema is initialized at startup. Database
files and `.env` are ignored by Git.

## Agent API

- `POST /api/v1/agents/sessions` with `{}` (or a `title`) creates a conversation.
- `GET /api/v1/agents/sessions` lists conversations.
- `GET /api/v1/agents/sessions/{id}` retrieves a conversation.
- `GET /api/v1/agents/sessions/{id}/events` retrieves ordered history.
- `DELETE /api/v1/agents/sessions/{id}` deletes it.
- `WS /api/v1/agents/sessions/{id}/ws` replays history, then
  accepts `{"command": "prompt", "prompt": "Help plan our sprint"}`. Frames
  include `session`, `history.start`, `agent.event` (with a Hyperforge event in
  `event`), `history.end`, and `session.ready`. The socket also accepts
  `steer` (`content`), `interrupt`, and `feedback_response` (`request_id`,
  `response`) commands. One socket per conversation may be active at a time.

There is no authentication or identity requirement; conversations and memories
are shared across API callers. Team scope is shared across conversations and survives
restart. Ask the agent to add, update, remove or list the team scope. `gh_cli` and
`acli` tools use separate argument strings (not shell commands), return exit status,
stdout and stderr, and require the CLIs to be installed and authenticated in the
backend process environment. The Docker image does not include those CLIs by default.
Custom `HarnessTool` implementations can also be passed to
`team_partner.app.create_app(tools=...)` for additional integrations.
