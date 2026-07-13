#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Wait for database if DATABASE_URL is set and uses postgres
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for database..."
    python << END
import sys
import time
import urllib.parse
import psycopg

db_url = "$DATABASE_URL"
if db_url.startswith("postgres"):
    parsed = urllib.parse.urlparse(db_url)
    dbname = parsed.path[1:]
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 5432
    
    attempts = 0
    while attempts < 30:
        try:
            conn = psycopg.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port,
                connect_timeout=2
            )
            conn.close()
            print("Database is ready!")
            sys.exit(0)
        except psycopg.OperationalError as e:
            attempts += 1
            print(f"Database not ready yet. Waiting...")
            time.sleep(1)
    print("Database connection timed out.")
    sys.exit(1)
END
fi

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting server..."
if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ]; then
    exec python manage.py runserver 0.0.0.0:8000
else
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
fi
