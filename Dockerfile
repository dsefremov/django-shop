# syntax=docker/dockerfile:1
# Образы Django Shop:
#   assets — сборка Tailwind CSS 4 (Node 22) → static/css/app.css;
#   base   — Python 3.13 + зависимости приложения;
#   dev    — base + тесты и статпроверки (pytest, ruff, mypy); код монтируется томом;
#   app    — production-образ: код + собранный CSS, Gunicorn.

FROM node:22-slim AS assets
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY assets ./assets
COPY templates ./templates
COPY accounts ./accounts
COPY catalog ./catalog
COPY cart ./cart
COPY orders ./orders
RUN mkdir -p static/css && npm run build:css

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
ARG UID=1000
ARG GID=1000
RUN groupadd -g "${GID}" app && useradd -u "${UID}" -g app -m -s /bin/bash app
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
USER app

FROM base AS app
COPY --chown=app:app . .
COPY --from=assets --chown=app:app /src/static/css/app.css static/css/app.css
RUN mkdir -p /app/staticfiles /app/media && chown app:app /app/staticfiles /app/media
USER app
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "--config", "docker/gunicorn.conf.py", "config.wsgi:application"]
