#!/bin/bash
set -e

# Set default port if not specified
export PORT=${PORT:-8000}

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z $SQL_HOST $SQL_PORT; do
  sleep 0.5
done
echo "Database is ready!"

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files - already done in Dockerfile but ensure it's updated
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Start Gunicorn server with proper signal handling
echo "Starting Gunicorn server on port $PORT..."
exec gunicorn app.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 2 \
    --timeout 120 \
    --worker-tmp-dir /dev/shm \
    --log-level=info \
    --access-logfile=- \
    --error-logfile=-