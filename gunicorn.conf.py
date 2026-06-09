bind = "127.0.0.1:5000"
workers = 2
worker_class = "sync"
timeout = 60
keepalive = 5
errorlog = "/opt/srcn/logs/gunicorn_error.log"
accesslog = "/opt/srcn/logs/gunicorn_access.log"
loglevel = "warning"
