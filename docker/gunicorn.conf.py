#!/usr/bin/env python3

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'uvicorn.workers.UvicornWorker'
worker_connections = 1000
timeout = 300
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# Logging
loglevel = 'info'
accesslog = '/app/logs/access.log'
errorlog = '/app/logs/error.log'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# Process naming
proc_name = 'language-toolkit-api'

# Server mechanics
preload_app = True
daemon = False
pidfile = '/app/logs/gunicorn.pid'
user = None
group = None
tmp_upload_dir = '/app/temp'

# SSL (uncomment if using SSL)
# keyfile = '/app/ssl/server.key'
# certfile = '/app/ssl/server.crt'