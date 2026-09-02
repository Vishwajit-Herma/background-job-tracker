#!/usr/bin/env bash
set -e

echo "Running database migrations..."
python manage.py migrate --noinput

echo "Starting Celery worker..."
celery -A config worker --loglevel=info --pool=solo --concurrency=1 &
WORKER_PID=$!

echo "Starting Celery beat..."
celery -A config beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler &
BEAT_PID=$!

cleanup() {
    echo "Stopping background processes..."
    kill "$WORKER_PID" "$BEAT_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
    wait "$BEAT_PID" 2>/dev/null || true
}

trap cleanup SIGTERM SIGINT

echo "Starting Gunicorn..."
gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 \
    --timeout 120 &
GUNICORN_PID=$!

wait "$GUNICORN_PID"
STATUS=$?

cleanup

exit "$STATUS"