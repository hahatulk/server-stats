"""Linux container entrypoint. Start exactly one collector in the worker."""
import os
import threading

bind = f"{os.environ.get('SERVER_STATS_HOST', '0.0.0.0')}:{int(os.environ.get('SERVER_STATS_PORT', '5000'))}"
workers = 1
worker_class = "gthread"
threads = 4
preload_app = False
worker_tmp_dir = "/tmp"
accesslog = "-"
errorlog = "-"


def post_worker_init(worker):
    # Gunicorn imports server_stats without executing its __main__ block.
    # Start after fork: no background thread or mutable snapshot is inherited.
    from server_stats import stats_collector

    collector = threading.Thread(target=stats_collector, name="stats-collector", daemon=True)
    collector.start()
