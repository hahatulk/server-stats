"""Small Flask server exposing host resource statistics.

The legacy ``/stats`` response deliberately keeps its first six semicolon
separated fields unchanged; new fields are appended to that response.
"""
import os
import socket
import threading
import time

from flask import Flask, abort, jsonify
import psutil

# Linux Docker mounts the VM's procfs here. Set before psutil's first sample.
# Windows EXE keeps the native psutil configuration unchanged.
if os.name == "posix" and os.environ.get("SERVER_STATS_PROCFS"):
    psutil.PROCFS_PATH = os.environ["SERVER_STATS_PROCFS"]

app = Flask(__name__)

_STATS_LOCK = threading.Lock()
_DISK_PATH = os.environ.get("SERVER_STATS_DISK", os.path.abspath(os.sep))

# Keep these names and the first six /stats fields stable for existing clients.
current_stats = {
    "cpu": 0.0,
    "ram_percent": 0.0,
    "ram_used_gb": 0.0,
    "ram_total_gb": 0.0,
    "net_recv_mbps": 0.0,
    "net_sent_mbps": 0.0,
    "hostname": socket.gethostname().replace(";", "_").replace("\r", "_").replace("\n", "_"),
    "disk_percent": 0.0,
    "disk_used_gb": 0.0,
    "disk_total_gb": 0.0,
    "disk_read_mbps": 0.0,
    "disk_write_mbps": 0.0,
}


def _snapshot():
    """Return an atomic copy suitable for a request handler."""
    with _STATS_LOCK:
        return dict(current_stats)


def _safe_hostname():
    # Delimiters would corrupt the legacy semicolon response.
    return socket.gethostname().replace(";", "_").replace("\r", "_").replace("\n", "_")


def _nonnegative_delta(now, before, elapsed):
    """Calculate a rate while tolerating reset/wrap and bad timestamps."""
    if elapsed <= 0 or now is None or before is None or now < before:
        return 0.0
    return max(0.0, (now - before) / elapsed)


def _disk_stats():
    try:
        usage = psutil.disk_usage(_DISK_PATH)
        used = round(usage.used / (1024 ** 3), 1)
        total = round(usage.total / (1024 ** 3), 1)
        percent = float(usage.percent)
    except (OSError, IOError, AttributeError, TypeError, ValueError):
        percent = used = total = 0.0
    return percent, used, total


def _collect_once(last_net, last_disk, last_time, now=None):
    """Collect one sample and return ``(sample, counters, timestamp)``."""
    now = time.monotonic() if now is None else now
    mem = psutil.virtual_memory()
    net = psutil.net_io_counters()
    disk_io = psutil.disk_io_counters()
    elapsed = now - last_time

    recv = _nonnegative_delta(net.bytes_recv, last_net.bytes_recv, elapsed) * 8 / 1000000
    sent = _nonnegative_delta(net.bytes_sent, last_net.bytes_sent, elapsed) * 8 / 1000000
    read = write = 0.0
    if disk_io is not None and last_disk is not None:
        # Decimal megabytes per second (MB/s), not megabits or MiB/s.
        read = _nonnegative_delta(disk_io.read_bytes, last_disk.read_bytes, elapsed) / 1000000
        write = _nonnegative_delta(disk_io.write_bytes, last_disk.write_bytes, elapsed) / 1000000
    disk_percent, disk_used, disk_total = _disk_stats()
    sample = {
        "cpu": float(psutil.cpu_percent(interval=None)),
        "ram_percent": float(mem.percent),
        "ram_used_gb": round(mem.used / (1024 ** 3), 1),
        "ram_total_gb": round(mem.total / (1024 ** 3), 1),
        "net_recv_mbps": round(recv, 6),
        "net_sent_mbps": round(sent, 6),
        "hostname": _safe_hostname(),
        "disk_percent": disk_percent,
        "disk_used_gb": disk_used,
        "disk_total_gb": disk_total,
        "disk_read_mbps": round(read, 1),
        "disk_write_mbps": round(write, 1),
    }
    return sample, net, disk_io, now


def stats_collector():
    last_net = psutil.net_io_counters()
    last_disk = psutil.disk_io_counters()
    last_time = time.monotonic()
    while True:
        try:
            sample, last_net, last_disk, last_time = _collect_once(
                last_net, last_disk, last_time
            )
            with _STATS_LOCK:
                current_stats.clear()
                current_stats.update(sample)
        except (OSError, IOError, AttributeError, TypeError, ValueError):
            # A transient psutil failure must not terminate the service thread.
            pass
        time.sleep(1)


def _format_network_rate(value):
    # WebParser's decimal regexp does not accept Python's scientific notation.
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _format_stats(s):
    return (f"CPU:{s['cpu']};RAM:{s['ram_percent']};RAM_USED:{s['ram_used_gb']};"
            f"RAM_TOTAL:{s['ram_total_gb']};NET_RECV:{_format_network_rate(s['net_recv_mbps'])};"
            f"NET_SENT:{_format_network_rate(s['net_sent_mbps'])};HOSTNAME:{s['hostname']};"
            f"DISK_PERCENT:{s['disk_percent']};DISK_USED:{s['disk_used_gb']};"
            f"DISK_TOTAL:{s['disk_total_gb']};DISK_READ:{s['disk_read_mbps']};"
            f"DISK_WRITE:{s['disk_write_mbps']}")


@app.route("/stats")
def stats():
    return _format_stats(_snapshot())


@app.route("/api/stats")
def api_stats():
    return jsonify(_snapshot())


DEMO_LOADS = (10, 50, 80, 100)


def _demo_snapshot(load):
    if load not in DEMO_LOADS:
        abort(404, description="Available demo loads: 10, 50, 80, 100")
    # Synthetic values only: never mutate current_stats or run stress workloads.
    # Percentages apply to CPU, RAM and disk capacity. Network and disk I/O
    # have physical rate units, so show `load` Mbit/s and `load` MB/s respectively.
    return {
        "cpu": float(load),
        "ram_percent": float(load),
        "ram_used_gb": round(16 * load / 100, 1),
        "ram_total_gb": 16.0,
        "net_recv_mbps": float(load),
        "net_sent_mbps": float(load),
        "hostname": f"DEMO-{load}",
        "disk_percent": float(load),
        "disk_used_gb": round(256 * load / 100, 1),
        "disk_total_gb": 256.0,
        "disk_read_mbps": float(load),
        "disk_write_mbps": float(load),
    }


@app.route("/demo/<int:load>")
def demo_stats(load):
    return _format_stats(_demo_snapshot(load))


@app.route("/api/demo/<int:load>")
def demo_api_stats(load):
    return jsonify(_demo_snapshot(load))


if __name__ == "__main__":
    t = threading.Thread(target=stats_collector, daemon=True)
    t.start()
    host = os.environ.get("SERVER_STATS_HOST", "0.0.0.0")
    try:
        port = int(os.environ.get("SERVER_STATS_PORT", "5000"))
    except ValueError:
        port = 5000
    app.run(host=host, port=port)
