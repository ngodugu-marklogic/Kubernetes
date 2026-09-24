FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Pin uv independently of changes to application dependencies.
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

EXPOSE 8888
CMD ["uv", "run", "--no-dev", "--no-sync", "team-partner-http"]
