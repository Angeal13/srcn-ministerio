import multiprocessing, os
bind = f"0.0.0.0:{os.environ.get('LAN_PORT', '5000')}"
workers = int(os.environ.get('GUNICORN_WORKERS', min(multiprocessing.cpu_count() * 2 + 1, 9)))
worker_class = "sync"
threads = 4
timeout = 120
keepalive = 10
accesslog = "/var/log/bioko_health/gunicorn_access.log"
errorlog  = "/var/log/bioko_health/gunicorn_error.log"
loglevel  = "warning"
pidfile   = "/run/bioko_health/gunicorn.pid"
user = "bioko"
group = "bioko"
daemon = False
