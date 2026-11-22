#!/usr/bin/env bash
# Проверки содержимого git (локально и в CI): в репозитории нет var/, .env, дампов, ключей и
# собранных файлов, а в отслеживаемых файлах нет литералов паролей, секретов и токенов.
# Проверяются только файлы из `git ls-files`. Запуск из корня: docker/check-repo.sh (код ≠ 0 — не прошла).
set -euo pipefail
cd "$(dirname "$0")/.."
fail=0
tracked() { git ls-files -z | tr '\0' '\n'; }

# 1. Секреты, локальные данные и сборка не отслеживаются.
bad=$(tracked | grep -E '^(var|media|staticfiles|node_modules|test-results|playwright-report)/|(^|/)\.env(\..*)?$|\.(sql|dump|sqlite3?|pem|key|p12|pfx)(\.gz)?$|(^|/)id_(rsa|ed25519)|^static/css/app\.css$' || true)
if [ -n "$bad" ]; then
    echo "В git попали секреты, локальные данные или сборка:"; echo "$bad"; fail=1
fi

# 2. Литералы паролей, секретов и токенов (значение — строка, а не переменная или файл).
pattern="(password|passwd|pwd|secret|secret_key|token|api_key)[0-9]*['\"]?[[:space:]]*(=>|=|:)[[:space:]]*['\"][^'\"\$[:space:]]{3,}['\"]"
hits=$(tracked | grep -vE '(^|/)package-lock\.json$|\.png$' | tr '\n' '\0' \
    | xargs -0 grep -nIiE "$pattern" -- 2>/dev/null || true)
if [ -n "$hits" ]; then
    echo "Похоже на пароль/секрет в коде:"; echo "$hits"; fail=1
fi

# 3. Пароли в переменных окружения compose/CI только через *_FILE или trust (без значений).
env_hits=$(tracked | grep -E '(^|/)(compose\.ya?ml|.*\.ya?ml)$' | tr '\n' '\0' \
    | xargs -0 grep -nE '(POSTGRES_PASSWORD|DB_PASSWORD|SECRET_KEY)[A-Z_]*:[[:space:]]*[^/[:space:]]' -- 2>/dev/null \
    | grep -vE '_FILE:[[:space:]]*/run/secrets/' || true)
if [ -n "$env_hits" ]; then
    echo "Пароль задан значением в YAML (нужен *_FILE):"; echo "$env_hits"; fail=1
fi

if [ "$fail" -ne 0 ]; then
    exit 1
fi
echo "check-repo: секретов, var/ и .env в git нет ($(tracked | wc -l) файлов проверено)."
