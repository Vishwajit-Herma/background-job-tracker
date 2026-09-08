# Process types for 12-factor app deployment
web: gunicorn config.asgi:application --bind 0.0.0.0:$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 50
worker: celery -A config worker --loglevel=info --concurrency=2
beat: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
flower: celery -A config flower --port=5555

