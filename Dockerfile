# syntax=docker/dockerfile:1
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so this layer is cached when source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini pyproject.toml ./
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN groupadd --system cheers \
    && useradd --system --gid cheers --create-home cheers \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && mkdir -p /app/logs \
    && chown -R cheers:cheers /app

USER cheers

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "app.main"]
