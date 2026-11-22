#!/usr/bin/env bash
# Установка с нуля: секреты в var/ → образы → PostgreSQL → миграции → суперпользователь и демо-данные →
# Gunicorn и nginx → тестовый PostgreSQL. Повторный запуск безопасен (секреты не перезаписываются,
# миграции идемпотентны, демо-данные загружаются заново).
# Запуск из корня репозитория: docker/setup.sh  (DC — команда compose, например DC="sudo docker compose").
# Порты — HTTP_PORT (8098), APP_PORT (8099), DB_PORT (54317), TEST_DB_PORT (54318).
set -euo pipefail
cd "$(dirname "$0")/.."
DC=${DC:-docker compose}
export UID GID=${GID:-$(id -g)}
step() { printf '\n==> %s\n' "$*"; }

step "Секреты (var/)"
docker/secrets.sh

step "Сборка образов (Tailwind CSS собирается в стадии assets)"
$DC build web tools

step "PostgreSQL 17"
$DC up -d --wait db

step "Миграции"
$DC run --rm --no-deps web python manage.py migrate --noinput

step "Суперпользователь и демо-данные"
$DC run --rm --no-deps web python manage.py ensure_superuser
$DC run --rm --no-deps web python manage.py seed_demo

step "Gunicorn и nginx"
$DC up -d --wait web nginx

step "Тестовый PostgreSQL (pytest)"
$DC up -d --wait test-db

step "Tailwind для локальных проверок (static/css/app.css)"
$DC run --rm node sh -c 'npm ci --no-audit --no-fund && npm run build:css'

echo
echo "Готово: http://127.0.0.1:${HTTP_PORT:-8098}  (админка: /admin/)"
echo "Учётные данные: var/admin-password (admin@django-shop.test), var/demo-users.json (менеджер и покупатели)."
