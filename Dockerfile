# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS wheel-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml MANIFEST.in README.md ./
COPY src/ ./src/
COPY --from=frontend-builder /app/src/interfaces/web/dist ./src/interfaces/web/dist
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels .

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRODUCTION=true \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8000 \
    XDG_CONFIG_HOME=/data/config \
    DATABASE_URL=sqlite+aiosqlite:////data/db/agens.db \
    WORKSPACE_ROOT=/workspace

RUN groupadd --system --gid 10001 agens \
    && useradd --system --uid 10001 --gid agens --home-dir /home/agens --create-home agens \
    && mkdir -p /data/config /data/db /data/memories /data/runtime /workspace \
    && chown -R agens:agens /data /workspace /home/agens

WORKDIR /app
COPY --from=wheel-builder /wheels /wheels
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels agens \
    && rm -rf /wheels

USER agens
EXPOSE 8000
VOLUME ["/data/config", "/data/db", "/data/memories", "/data/runtime", "/workspace"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["agens", "_run-interfaces", "web"]
