FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# uv needs Git to fetch the pinned Hyperforge source. The agent uses gh and acli
# for GitHub and Atlassian queries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates gh git gnupg wget \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && wget -qO- https://acli.atlassian.com/gpg/public-key.asc \
        | gpg --dearmor -o /etc/apt/keyrings/acli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/acli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/acli-archive-keyring.gpg] https://acli.atlassian.com/linux/deb stable main" \
        > /etc/apt/sources.list.d/acli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends acli \
    && rm -rf /var/lib/apt/lists/*

# Pin uv independently of changes to application dependencies.
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

EXPOSE 8888
CMD ["uv", "run", "--no-dev", "--no-sync", "team-partner-http"]
