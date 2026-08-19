#!/bin/bash
# Release phase script for 12-factor app
# This runs after build but before deployment

set -e

echo "===> Running release tasks..."

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

echo "===> Release tasks completed successfully!"
