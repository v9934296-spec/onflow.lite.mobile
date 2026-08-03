# Build from monorepo root: docker build -f services/api/Dockerfile .
# Wolfi base avoids unfixed perl CVEs in python:3.12-slim (Debian).
FROM cgr.dev/chainguard/wolfi-base
USER root
WORKDIR /app
RUN apk add --no-cache python-3.12 py3.12-pip ffmpeg
COPY services/api/requirements.txt .
RUN set -eux; \
    for i in 1 2 3 4 5; do \
        if python3.12 -m pip install --no-cache-dir \
            --retries 10 --timeout 120 --progress-bar off \
            -r requirements.txt; then \
            exit 0; \
        fi; \
        echo "pip install failed, retrying ($i/5)..." >&2; \
        sleep 5; \
    done; \
    echo "pip install failed after 5 attempts" >&2; \
    exit 1
COPY services/api/app ./app
COPY services/api/migrations ./migrations
COPY services/api/alembic.ini ./alembic.ini
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
RUN python3.12 -c "import fastapi, sqlmodel, arq, structlog, alembic, boto3, redis, pydantic_settings, slowapi, sentry_sdk"
RUN mkdir -p /app/data/uploads && chown -R nonroot:nonroot /app
USER nonroot
EXPOSE 8080
CMD ["sh", "-c", "python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
