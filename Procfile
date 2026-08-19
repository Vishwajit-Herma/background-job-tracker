# Process types for 12-factor app deployment
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --max-requests 1000 --max-requests-jitter 50 --timeout 30
worker: celery -A config worker --loglevel=info --concurrency=2
beat: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
flower: celery -A config flower --port=5555
