#!/bin/sh
# Run schema migrations before starting the bot. Retries briefly so a
# container can start at the same time as PostgreSQL.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    attempt=1
    while [ "$attempt" -le 10 ]; do
        if alembic upgrade head; then
            break
        fi
        if [ "$attempt" -eq 10 ]; then
            echo "Database migrations failed after 10 attempts." >&2
            exit 1
        fi
        echo "Migration attempt ${attempt} failed; retrying in 3s..." >&2
        attempt=$((attempt + 1))
        sleep 3
    done
fi

exec "$@"
