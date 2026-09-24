FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# uv needs Git to fetch the pinned Hyperforge source. The agent uses gh for GitHub queries.
RUN apt-get update && apt-get install -y --no-install-recommends gh git \
    && rm -rf /var/lib/apt/lists/*

# Pin uv independently of changes to application dependencies.
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

EXPOSE 8888
CMD ["uv", "run", "--no-dev", "--no-sync", "team-partner-http"]
