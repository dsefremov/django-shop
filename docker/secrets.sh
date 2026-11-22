#!/usr/bin/env bash
# Генерирует локальные секреты в var/ (каталог вне git). Существующие файлы не перезаписываются,
# поэтому повторный запуск безопасен. Пароли никуда не печатаются.
#   var/secrets/db-password       — PostgreSQL (POSTGRES_PASSWORD_FILE, DB_PASSWORD_FILE);
#   var/secrets/test-db-password  — тестовый PostgreSQL для pytest;
#   var/secrets/secret-key        — SECRET_KEY Django;
#   var/admin-password            — суперпользователь admin@django-shop.test (manage.py ensure_superuser);
#   var/demo-users.json           — демо-менеджер и демо-покупатели (manage.py seed_demo, e2e).
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p var/secrets
chmod 700 var var/secrets

gen() { python3 -c 'import secrets; print(secrets.token_urlsafe(24))'; }

for name in db-password test-db-password; do
    if [ ! -s "var/secrets/$name" ]; then
        gen > "var/secrets/$name"
        echo "Создан var/secrets/$name"
    fi
    # PostgreSQL в контейнере читает файл от своего пользователя (bind mount secrets): нужен доступ
    # на чтение; снаружи файл закрыт каталогом var/ (700).
    chmod 644 "var/secrets/$name"
done

if [ ! -s var/secrets/secret-key ]; then
    python3 -c 'import secrets; print(secrets.token_urlsafe(50))' > var/secrets/secret-key
    echo "Создан var/secrets/secret-key"
fi

if [ ! -s var/admin-password ]; then
    gen > var/admin-password
    echo "Создан var/admin-password"
fi

if [ ! -s var/demo-users.json ]; then
    python3 - <<'PY'
import json
import secrets

users = {
    key: {"email": f"{key}@django-shop.test", "password": secrets.token_urlsafe(18)}
    for key in ("manager", "customer", "maria")
}
with open("var/demo-users.json", "w", encoding="utf-8") as fh:
    json.dump(users, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY
    echo "Создан var/demo-users.json"
fi
chmod 600 var/secrets/secret-key var/admin-password var/demo-users.json
