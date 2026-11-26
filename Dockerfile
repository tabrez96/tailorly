# Builds the vendored htmx, Alpine and font files from package-lock.json.
FROM node:24-slim AS vendor
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY scripts/vendor.mjs scripts/vendor.mjs
RUN npm run vendor

FROM python:3.14-slim-trixie
# postgresql-client-18 (pg_dump for manage.py backup) comes from the PostgreSQL apt repository.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates postgresql-common \
    && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv
RUN groupadd --system --gid 10001 tailorly \
    && useradd --system --uid 10001 --gid tailorly --home-dir /app --no-create-home tailorly
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MEDIA_ROOT=/data/media \
    BACKUP_DIR=/data/backups
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev
COPY . .
COPY --from=vendor /app/static/vendor static/vendor
ARG ASSET_VERSION=""
ENV ASSET_VERSION=$ASSET_VERSION
# Settings need these to load; collectstatic touches neither.
RUN SECRET_KEY=collectstatic-only DATABASE_URL=postgres:///unused python manage.py collectstatic --noinput
RUN install -d -o tailorly -g tailorly /data/media /data/backups
USER tailorly
EXPOSE 8000 8001
CMD ["gunicorn", "config.wsgi", "--workers", "2", "--bind", "0.0.0.0:8000", "--access-logfile", "-"]
