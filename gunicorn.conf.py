import os

bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = int(os.environ.get("GUNICORN_WORKERS", 2))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
timeout = 60
graceful_timeout = 30
keepalive = 5
worker_tmp_dir = "/dev/shm"
accesslog = "-"
errorlog = "-"
# Sin preload_app: cada proceso carga su propia sesión de onnxruntime (Fase 7).
