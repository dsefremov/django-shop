#!/usr/bin/env bash
# Полный раунд проверок на локальном стенде (docker/setup.sh уже выполнен). Любой ненулевой код —
# раунд красный. Запуск из корня репозитория: docker/round.sh (DC — команда compose, по умолчанию
# «docker compose», например DC="sudo docker compose"). Playwright запускается на хосте (npx) против
# http://127.0.0.1:${HTTP_PORT:-8098}.
set -euo pipefail
cd "$(dirname "$0")/.."
DC=${DC:-docker compose}
export UID GID=${GID:-$(id -g)}
run() { printf '\n==> %s\n' "$*"; "$@"; }
tools() { $DC run --rm -T tools "$@"; }

echo "Коммит: $(git rev-parse --short HEAD)$(git diff --quiet HEAD -- . ':!docs/screenshots' || echo ' (+ незакоммиченные правки)')"
run docker/check-repo.sh
run $DC build -q web tools
run tools ruff format --check .
run tools ruff check .
run tools mypy .
run tools python manage.py check
run tools python manage.py makemigrations --check --dry-run
run $DC run --rm -T node npm run build:css
run $DC run --rm -T node npm run types:check
run $DC up -d --wait test-db
run tools pytest -p no:cacheprovider
run $DC up -d --wait web nginx
run $DC exec -T web python manage.py migrate --noinput
run $DC exec -T web python manage.py seed_demo
run npx playwright test --project=e2e
echo
echo "РАУНД ЗЕЛЁНЫЙ"
