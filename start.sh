#!/bin/sh
exec gunicorn app.wsgi:application --bind 0.0.0.0:${PORT:-8000}