"""Gunicorn settings. Start with: gunicorn config.wsgi (Linux; `uv sync --extra production`)."""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000  # recycle workers periodically to contain memory growth
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")
