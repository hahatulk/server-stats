"""Run inside the image via stdin; no host Python dependencies are needed.

    docker run --rm -i --network none --read-only --cap-drop ALL \
        --security-opt no-new-privileges \
        --tmpfs /tmp:rw,noexec,nosuid,size=16m,mode=1777 \
        --entrypoint python server-stats:alpine - < tests/smoke_docker_runtime.py
"""
import os
import time

import gunicorn
import psutil
import server_stats

assert os.getuid() == 65534
sample, *_ = server_stats._collect_once(
    psutil.net_io_counters(), psutil.disk_io_counters(), time.monotonic() - 1
)
assert sample["ram_total_gb"] > 0
assert sample["disk_total_gb"] > 0
client = server_stats.app.test_client()
assert client.get("/api/stats").status_code == 200
assert client.get("/api/demo/80").get_json()["cpu"] == 80
assert gunicorn.__version__
print("Alpine runtime smoke test passed: psutil, Gunicorn, Flask, non-root, read-only filesystem")
