"""Gunicorn за nginx: слушает только 127.0.0.1 (сеть хоста), порт — APP_PORT."""

import multiprocessing
import os

bind = f"127.0.0.1:{os.environ.get('APP_PORT', '8099')}"
workers = int(os.environ.get("GUNICORN_WORKERS", min(4, multiprocessing.cpu_count() * 2 + 1)))
threads = 2
timeout = 30
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "127.0.0.1"
