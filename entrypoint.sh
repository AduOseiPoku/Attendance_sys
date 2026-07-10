#!/usr/bin/env bash
set -e

# Wait for the DB to be ready (if using postgres)
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for database..."
    while ! python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); django.setup(); from django.db import connections; connections['default'].ensure_connection()" 2>/dev/null; do
        sleep 1
    done
fi

# Apply migrations
echo "Running migrations..."
python manage.py migrate --noinput

# Collect static assets (required for production)
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Finally start the app
echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}
