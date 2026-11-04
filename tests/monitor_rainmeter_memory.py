"""Sample actual Rainmeter private bytes without restarting it or trimming memory.

Run after installing/reloading the updated skin. Close unrelated skins for an
isolated comparison. This measures the entire Rainmeter process, not one skin.
Example: py tests/monitor_rainmeter_memory.py --minutes 60 --csv rainmeter-memory.csv
"""
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import time

import psutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--minutes", type=float, default=60)
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--warmup", type=float, default=60, help="Seconds before baseline")
    parser.add_argument("--csv", type=Path, default=Path("rainmeter-memory.csv"))
    args = parser.parse_args()
    if not 0 < args.minutes <= 1440 or args.interval < 1 or not 0 <= args.warmup < args.minutes * 60:
        parser.error("minutes: (0, 1440]; interval >= 1; 0 <= warmup < duration")
    if args.pid:
        process = psutil.Process(args.pid)
    else:
        matches = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "rainmeter.exe"]
        if len(matches) != 1:
            parser.error("Expected one Rainmeter.exe process; use --pid to select one")
        process = matches[0]
    started = time.monotonic()
    duration = args.minutes * 60
    baseline = last = peak = None
    count = 0
    sx = sy = sxx = sxy = 0.0
    print(f"PID {process.pid}; duration {args.minutes:g} min; CSV: {args.csv}", flush=True)
    with args.csv.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["utc", "elapsed_s", "private_mib", "working_set_mib", "handles"])
        while True:
            elapsed = time.monotonic() - started
            try:
                info = process.memory_info()
                private = getattr(info, "private", info.vms) / (1024 ** 2)
                handles = process.num_handles() if hasattr(process, "num_handles") else ""
            except psutil.Error as error:
                raise SystemExit(f"Process unavailable; measurement stopped: {error}")
            writer.writerow([datetime.now(timezone.utc).isoformat(), round(elapsed, 2), round(private, 3), round(info.rss / (1024 ** 2), 3), handles])
            output.flush()
            if elapsed >= args.warmup:
                baseline = private if baseline is None else baseline
                last = private
                peak = private if peak is None else max(peak, private)
                count += 1
                x = (elapsed - args.warmup) / 60
                sx += x
                sy += private
                sxx += x*x
                sxy += x*private
            print(f"{elapsed:7.1f}s  private={private:8.2f} MiB  handles={handles}", flush=True)
            if elapsed >= duration:
                break
            time.sleep(min(args.interval, duration-elapsed))
    if baseline is not None:
        denominator = count*sxx - sx*sx
        slope = (count*sxy - sx*sy)/denominator if denominator else 0.0
        print(f"After warmup: change={last-baseline:+.2f} MiB; peak={peak:.2f} MiB; trend={slope:+.3f} MiB/min")
    print("Compare sustained trends under the same workload, both with online and offline VMs.")


if __name__ == "__main__":
    main()
