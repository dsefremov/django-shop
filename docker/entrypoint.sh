#!/usr/bin/env bash
# Точка входа контейнера web: статика в общий с nginx том, затем команда (Gunicorn по умолчанию).
set -euo pipefail
python manage.py collectstatic --noinput --clear -v 0
exec "$@"
