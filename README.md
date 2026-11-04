# ServerStats — compact VM monitor for Rainmeter

**Project description, change history, and web-section reference:** [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).

The old standalone skin `ServerStats/ServerStats_Win10.ini` is preserved. The aggregated widget is available in **20 ready-made variants**: `ServerStats/Aggregate/Aggregate-01.ini` … `Aggregate-20.ini` (from 1 to 20 rows). `Aggregate.ini`, which sizes itself automatically for the entire list, is also included.

## What the new widget shows

- At the top: the physical host / hypervisor name configured by `host_title`.
- Each row contains the agent hostname, connection address, CPU in %, network ↓ receive / ↑ send in Mbit/s, compact RAM in the format `3.2 / 8.0 GB (40%)`, disk in the format `128.0 / 256.0 GB` (without a separate percentage), and disk I/O: **R — read / W — write in MB/s**.
- Nearly opaque dark background `12,12,12,250`, rounded corners, Segoe UI; blue CPU, purple RAM, orange NETWORK, green DISK. Under CPU and RAM are **36 px** graphs in Win10 Widgets RU 2.0 style: line, translucent fill, and border, with a fixed 0–100% scale. Row height is 88 px. The hostname/IP column is narrowed to 140 px; the full name is available in the tooltip. The NETWORK column is widened to 146 px for the line `↓1000.0 ↑1000.0 Mbit/s` at font size 9: receive and send appear on one line separated by a space, for example `↓12.3 ↑1.2 Mbit/s`. Units are selected automatically according to the larger of the two speeds: **Kbit/s** below 1 Mbit/s, **Mbit/s** from 1 to 1000 Mbit/s, and **Gbit/s** from 1000 Mbit/s. Decimal conversion is used: 1000 Kbit/s = 1 Mbit/s, 1000 Mbit/s = 1 Gbit/s. When speed decreases, units switch back; at zero, Kbit/s is shown.
- The 36 px NETWORK graph has two lines in download/upload colors and one shared automatic scale. History is stored in source Mbit/s regardless of displayed units: switching Kbit/s ↔ Mbit/s ↔ Gbit/s does not distort earlier points. The label and tooltips use the selected units.
- The DISK block is split: **on the left**, colored R/W speeds and a green total-I/O graph (read + write in MB/s); **to the right of the graph**, a pie chart of usage, with used/total capacity below it. Units appear next to values, not in headings: capacity — `128.0 / 256.0 GB`, speeds — `R 12.5 W 3.2 MB/s`. The disk-capacity field is widened to 130 px. Values and column labels are centered relative to their graphs; hostname/IP remains on the left. GB is a visual label; capacities are still calculated by the agent in 1024³ bytes. The I/O graph is **36 px** high, auto-scaled, and aligned with the CPU, RAM, and NETWORK graphs; the current total is shown in the tooltip. All graph histories are limited by their widths and do not grow indefinitely.
- In disk I/O, `R` (read) uses the NETWORK download color and `W` (write) uses the upload color. Colors are controlled by the generator's shared `DownloadColor` and `UploadColor` variables; during a warning both values temporarily become red.
- All CPU, RAM, NETWORK, disk-capacity, and R/W-speed values use font size **9** at scale 1.0. CPU and RAM values, including the percentage in parentheses, are gray (`178,178,178`) in normal state, as is used disk capacity.
- At **CPU ≥ 80%**, **RAM ≥ 80%**, or **disk usage ≥ 80%**, the corresponding numeric values turn red. For DISK, the pie chart, capacity, and I/O values turn red (the I/O graph remains green), but the threshold is checked against usage, not MB/s. Below 80%, the normal color returns. The threshold is compared with the original value before rounding.
- A green dot means data was received; gray means waiting; red means a connection error or an incompatible agent version. On error, numeric indicators are hidden instead of remaining as stale “live” values. Error detection depends on the WebParser network timeout.

**All variants use one configuration file:** `@Resources/Aggregate/servers.json`. The generator creates a shared `servers.inc` from it, and every variant includes that file: IPs, ports, fallback names, and the host name are not duplicated across 20 files. Edit only the JSON, not `servers.inc` or generated INIs.

`Aggregate-NN.ini` shows the first NN **enabled** machines from the shared list. If there are fewer machines, remaining rows show “not configured” and make no network requests. If there are more, extra machines are not displayed or queried by that variant: choose a larger one. Order follows the JSON; `enabled: false` removes an entry from numbering.

After adding a machine, save the shared JSON, click **refresh** (or run `rebuild_aggregate.cmd`), then select the skin with the required number of rows. Rebuilding immediately updates **all 20 variants** and automatic `Aggregate.ini`. Changing JSON alone has no effect until rebuilding.

All 20 variants are in one configuration, `ServerStats → Aggregate`, so loading another variant replaces the previous one rather than running 20 polling sets in parallel. Automatic `Aggregate.ini` shows all enabled machines without the 20-row limit. Live resizing with the mouse is not implemented.

**List layout:** up to 10 slots use one column. Starting with the **11-slot** variant, two columns appear: VMs 1–10 on the left and VMs 11–20 on the right. All row data, graphs, pie chart, and statuses move together. Metric headings repeat above each column; a divider separates the columns. The host name and buttons remain in the shared header. In automatic `Aggregate.ini`, the second column is enabled at 11 active machines; if there are more than 20, the right column continues downward.

At scale 1.0, size for 10 slots is approximately **828 × 952 px**, and for 11–20 slots **1672 × 952 px**. To fit the widget to the screen, change the shared `scale` and rebuild the variants.

## Quick start

1. **Run the agent on every VM.** On **Windows**, use `server_stats.exe` from the project root. On **Linux**, use Docker Compose (instructions below). For development, the Python version can also be run:
   ```powershell
   py -m pip install -r requirements.txt
   py server_stats.py
   ```
   The old EXE without hostname/disk/I/O is not suitable for the new skin. Default port is TCP 5000. Check: `http://VM-IP:5000/stats`.
2. Copy the **entire `ServerStats` folder** to the Rainmeter skins directory (usually `Documents\Rainmeter\Skins`). For convenience, open the directory through Rainmeter → Manage → Open folder.
3. On the Rainmeter computer, install **Python 3.9+ with Python Launcher (`py.exe`)**. A ready INI can be loaded without Python, but Python is required to add/remove machines and change scale. The generator does not require Flask or psutil.
4. In the **copied folder**, open `@Resources/Aggregate/servers.json`:
   - replace `HYPERVISOR-01` with your host name;
   - replace the ten demo addresses `192.168.1.101`–`192.168.1.110` with real ones;
   - add/remove the required entries.
5. Run `ServerStats/rebuild_aggregate.cmd`, or execute the command below from the `ServerStats` folder.
6. In Rainmeter, click **Refresh all**, then load, for example, `ServerStats → Aggregate → Aggregate-10.ini`. The same folder contains `Aggregate-01.ini` … `Aggregate-20.ini` and automatic `Aggregate.ini`. After later rebuilds, the skin updates automatically if Rainmeter is found in PATH or in standard `Program Files`.

**Do not edit generated `Aggregate*.ini` or `servers.inc`**: changes will be overwritten. If you keep editing the original project folder after copying, the installed skin will not change — configure the copy in `Skins`.

## Configuration

File `ServerStats/@Resources/Aggregate/servers.json` (UTF-8, without comments):

```json
{
  "host_title": "PVE-01",
  "scale": 0.85,
  "update_seconds": 2,
  "servers": [
    {"id": "database", "address": "192.168.1.11", "port": 5000, "name": "db-01", "enabled": true},
    {"id": "web", "address": "192.168.1.12", "port": 5000, "name": "web-01", "enabled": true}
  ]
}
```

- `host_title` — heading, not an address for polling a hypervisor. Its metrics are not requested.
- `scale` — scale for all sizes and fonts, from 0.6 to 2.0.
- `update_seconds` — HTTP polling and graph-sampling interval for an available VM, from 1 to 3600 seconds. CPU, RAM, NETWORK, and disk-I/O graphs add a point at this interval (2 seconds by default), not on every 1-second Rainmeter tick. Metric values and the disk pie chart use the same update divider, so the displayed numbers and graph points refresh on the same tick. After an error, polling repeats no more than once per `max(30, update_seconds)` seconds; after recovery, the normal frequency returns.
- `id` — unique identifier: Latin letters, digits, `_`, `-`.
- `address` — IPv4/IPv6 address or DNS name. To display an IP specifically, enter an IP; a DNS name is not automatically converted to an IP.
- `port` — agent port; default 5000.
- `name` — fallback name until hostname is received. After a successful poll, the **actual VM hostname** is displayed.
- `enabled: false` — remove a machine from the widget while preserving its settings.
- Row order follows the order of enabled entries in `servers`. An empty list is supported. Fixed variants have 1–20 slots; automatic `Aggregate.ini` has no 20-machine limit.

After saving, click **refresh** in the widget header. The **list** button opens the JSON in Notepad. The same commands are available in the skin context menu. JSON is not watched automatically.

### Add/remove commands

From the **installed** `ServerStats` folder:

```powershell
# Rebuild and refresh the active skin
py "@Resources\Aggregate\generate.py" --refresh

# Add a machine and immediately change widget size
py "@Resources\Aggregate\generate.py" --refresh add 192.168.1.25 --id vm25 --name vm-25 --port 5000

# Remove by id
py "@Resources\Aggregate\generate.py" --refresh remove vm25

# List all entries, including disabled ones
py "@Resources\Aggregate\generate.py" list
```

On JSON errors, the existing INI is not overwritten. To see the error conveniently, run the command in a terminal or run `rebuild_aggregate.cmd`. If Rainmeter is installed in a non-standard directory, refresh the skin manually or add the directory containing `Rainmeter.exe` to PATH.

## Linux: running the agent in Docker

The container runs **on every monitored Linux VM**. Docker Engine and the Docker Compose plugin are required. One `compose.yaml` contains two services: **server-stats** for Docker Desktop (started by default) and **server-stats-linux** for the regular Linux Docker Engine. Rootless Docker is not supported for host monitoring. On Linux, explicitly specify the service name: this enables its profile and does not start the Desktop service. No `.env` is needed to select the mode; do not set `COMPOSE_PROFILES=linux` together with normal `up`, or both services will be selected.

From the project root on Linux:

```bash
# Optional: configure listening address, port, and filesystem
cp docker.env.example .env
# Edit .env if needed

docker compose up -d --build server-stats-linux
docker compose ps
curl http://127.0.0.1:5000/stats
curl http://127.0.0.1:5000/api/stats
```

If Docker requires elevated privileges, run commands with `sudo`. In `servers.json` on the Rainmeter computer, specify the **Linux VM** IP and agent port — the data format is the same as for the Windows EXE. If a specific `SERVER_STATS_HOST` was set in `.env`, check that address instead of `127.0.0.1`.

### Metrics collected

- The host `/proc` is mounted read-only at `/host/proc`; `SERVER_STATS_PROCFS` directs psutil to this data. CPU and RAM refer to the VM, not container limits.
- `network_mode: host` measures VM interface traffic. No `ports` section is needed: the server listens directly on the host port.
- `uts: host` returns the real VM hostname.
- `/sys` is connected read-only for device information and disk counters.
- The host `/` is mounted read-only at `/host/root`. By default, usage of the VM root filesystem, not the container image filesystem, is shown. I/O is summed across disks returned by psutil.

To show usage of the `/data` partition, set in `.env`:

```dotenv
SERVER_STATS_HOST=0.0.0.0
SERVER_STATS_PORT=5000
SERVER_STATS_DISK=/host/root/data
```

The path is specified **inside the container**. For `/`, use `/host/root`; for `/mnt/storage`, use `/host/root/mnt/storage`. A separate partition must be mounted on the Linux host before starting the container; recreate the container after changing mounts. Quote values containing spaces in `.env`.

```bash
# Apply .env changes
docker compose up -d --force-recreate server-stats-linux

# Update the agent after changing source/dependencies
docker compose up -d --build server-stats-linux

# Logs and shutdown
docker compose --profile linux logs --tail=100 -f server-stats-linux
docker compose --profile linux down
```

Docker uses **Gunicorn: one worker, four HTTP threads, and a separate collection thread running once per second**. The container starts automatically after Docker restarts (`unless-stopped`), has a healthcheck, and limits log size. `unhealthy` alone does not restart the container: check logs and access permissions for metrics/disk.

**Security:** the container runs as unprivileged UID 65534, without capabilities, Docker socket, or `privileged`. However, bind-mounting the host root and `/proc` grants read access to host data available to this UID — an intentional monitoring compromise. Do not use this image for untrusted code. Strict SELinux/AppArmor policies may deny access: configure permissions without disabling protection entirely and without adding `:Z` to system directories `/`, `/proc`, `/sys`.

With host networking, the port is not protected by Docker isolation. Restrict incoming TCP 5000 (or your port) on the VM itself to the Rainmeter computer's address. The agent has no TLS or authentication.

**Windows:** Docker is not required; starting `server_stats.exe` and environment parameters remain unchanged.

### Updating network-speed precision

For correct display of small traffic in Kbit/s, update the agent as well: the previous version rounded NETWORK to 0.1 Mbit/s (100 Kbit/s), and the skin cannot restore those lost values. The new version preserves six decimal places of Mbit/s; `/stats` returns them in ordinary decimal notation compatible with WebParser. Field format is unchanged.

- **Windows:** the higher-precision build is **`server_stats_updated.exe`** (also in `dist/server_stats.exe`). The current root `server_stats.exe` was occupied by a running process and was not overwritten. Stop the old agent, replace it with the new build (rename it to `server_stats.exe` if necessary), and start it again. The update does not try to stop a running agent automatically.
- **Linux Docker:** update sources on the VM and run `docker compose up -d --build server-stats-linux`.
- **Rainmeter:** update `@Resources/Aggregate/generate.py`, preserve your JSON, and run `rebuild_aggregate.cmd`.

## Docker Desktop on Windows: availability check

The `linux` profile in the shared `compose.yaml` uses `network_mode: host`. In Docker Desktop this is not the Windows network: without separately enabled host-networking support, the container may be `healthy` while `localhost:5000` does not respond in Windows. The `PORTS` column has no published port in this case. The internal healthcheck does not test availability from Windows.

Docker Desktop is the default mode **in the same `compose.yaml`**: service `server-stats` uses bridge networking and explicitly publishes the port. No separate override file, profile, or `.env` is needed for normal startup:

```powershell
docker compose up -d --build
docker compose ps
curl.exe http://127.0.0.1:5000/stats
```

`PORTS` should show `127.0.0.1:5000->5000/tcp`. By default, access is only from the current computer; for this Rainmeter check, use `127.0.0.1`. Inside the container the server forcibly listens on `0.0.0.0`, even if a different `SERVER_STATS_HOST` is specified for Linux in `.env`.

If port 5000 is busy, add `SERVER_STATS_PUBLISH_PORT=5001` to `.env` and run the same startup command. The Windows-side URL is then `http://127.0.0.1:5001/stats`. To allow LAN access, set `SERVER_STATS_PUBLISH_HOST=0.0.0.0` and restrict the incoming port in Windows Firewall to the trusted Rainmeter address. Do not expose the agent to the Internet.

**Important:** this mode shows metrics of the Docker Desktop Linux environment (for example hostname `docker-desktop`), not Windows. For real Windows metrics, use the EXE. For Linux VM metrics, run `docker compose up -d --build server-stats-linux` directly on that VM.

To stop:

```powershell
docker compose down
```

When changing modes, first run `docker compose --profile linux down`, then start the required service: do not run both simultaneously. During migration from the old Linux Compose setup, the service was named `server-stats`; stopping it before starting new `server-stats-linux` is required so the old container does not occupy the port. Shared image, metric, healthcheck, and limit settings are defined once through a YAML anchor.

If a problem occurs on a real Linux host, check `docker compose --profile linux logs --tail=100`, local `curl http://127.0.0.1:5000/stats`, `SERVER_STATS_HOST`, and firewall rules. With `network_mode: host`, no `PORTS` entry on Linux is normal — the listening port is directly on the host.

## Demo routes: 10 / 50 / 80 / 100

The agent provides four fixed demo states. They **create no load**, do not change real metrics, and do not interfere with `/stats` or `/api/stats`.

| State | Rainmeter format | JSON |
|---|---|---|
| 10 | `/demo/10` | `/api/demo/10` |
| 50 | `/demo/50` | `/api/demo/50` |
| 80 | `/demo/80` | `/api/demo/80` |
| 100 | `/demo/100` | `/api/demo/100` |

Example: `http://127.0.0.1:5000/demo/80`. An unknown state returns 404. Hostname is `DEMO-80`, so test data cannot be mistaken for real data.

In state N: CPU, RAM, and disk usage = **N%**; RAM = N% of 16 GiB, disk = N% of 256 GiB. NETWORK: receive and send at **N Mbit/s**; disks: read and write at **N MB/s**, meaning total I/O = 2N MB/s. NETWORK and I/O are speeds, not percentages. Values are constant, so graphs become horizontal after history fills. At 80 and 100, red CPU, RAM, and disk-usage warnings are checked.

### Show a demo in the widget

In shared `servers.json`, add an entry with `demo_load`:

```json
{"id": "demo80", "address": "127.0.0.1", "port": 5000, "name": "DEMO-80", "enabled": true, "demo_load": 80}
```

Or use the CLI from the installed `ServerStats` folder:

```powershell
py "@Resources\\Aggregate\\generate.py" --refresh add 127.0.0.1 --id demo80 --demo-load 80
```

A ready example of all four states is in **`@Resources/Aggregate/servers.demo.json`**. First save your working `servers.json`, then copy the demo example contents into it, run `rebuild_aggregate.cmd`, and select `Aggregate-04.ini`. For a remote agent, replace `127.0.0.1` with its address. All four rows may query one server. To return to real data, remove `demo_load` or set it to `null`, then rebuild the skin.

New routes require an updated agent: replace the EXE or run `docker compose up -d --build` (on Linux, `docker compose up -d --build server-stats-linux`).

## Agent: disk and startup parameters

The **DISK** column shows filesystem usage (with a GB label and no percentage; capacity is calculated in 1024³ bytes) and **I/O speed: R — read, W — write in MB/s** (1 MB = 1,000,000 bytes). I/O is summed across guest-OS disks returned by psutil; it is not activity percentage or the speed of one mount point. If the OS provides no I/O counters, 0.0 is shown. `SERVER_STATS_DISK` affects usage only. The default is the system root (`C:\` on ordinary Windows, `/` on Linux). For another disk / mount point:

```powershell
$env:SERVER_STATS_DISK = 'D:\'
$env:SERVER_STATS_PORT = '5000'
$env:SERVER_STATS_HOST = '0.0.0.0'
.\server_stats.exe
```

On Linux: `SERVER_STATS_DISK=/data python3 server_stats.py`.

`/stats` preserves the first six fields of the old protocol, so the old standalone skin continues to work. `HOSTNAME`, `DISK_PERCENT`, `DISK_USED`, `DISK_TOTAL`, `DISK_READ`, and `DISK_WRITE` are added afterward. `/api/stats` additionally returns JSON; despite their historical names, `disk_read_mbps` and `disk_write_mbps` mean **MB/s**, not Mbit/s. To show I/O, update the agent on the VMs and the skin together: an agent without `DISK_READ`/`DISK_WRITE` is marked incompatible by the new skin. NETWORK values are summed across guest-OS interfaces.

The agent has no authentication or TLS. Open the port **only to the Rainmeter computer on a trusted LAN/VPN**; do not publish it to the Internet. The Windows EXE uses the built-in Flask server for a small local monitor; Linux Docker uses Gunicorn.

## Rainmeter memory during long operation

The updated aggregate skin does not call `!UpdateMeter *` / `!Redraw` after every HTTP request and does not recreate the indicator Shape on every response. The three dot states have fixed geometry; visibility changes only when switching online/offline. Static backgrounds, dividers, headings, and addresses have `UpdateDivider=-1`; only live data is continuously updated. Automatic window-size recalculation is disabled because the generator already sets the size.

WebParser uses `Flags=ForceReload | NoCacheWrite | NoCookies`: statistics are not stored in the HTTP cache or WinINet cookie store. Connection errors do not cause cyclic redrawing of all rows; unavailable machines are polled less often. There are no automatic restarts, periodic refreshes, or forced working-set trimming — those would only mask the problem.

To apply the fix to an already configured skin:

1. Replace **only** `@Resources/Aggregate/generate.py` in the installed skin folder; do not overwrite your `servers.json`.
2. Run `rebuild_aggregate.cmd` to regenerate INIs with your addresses.
3. Fully close and restart Rainmeter once to release memory accumulated before the update. EXE and Docker agents do not need to be changed.

To check the result on your computer, install dependencies with `py -m pip install -r requirements.txt` and run from the project root:

```powershell
py tests/monitor_rainmeter_memory.py --minutes 60 --csv rainmeter-memory.csv
```

The script records **Private Bytes**, working set, and total Rainmeter-process handle count to CSV, and prints the memory trend after a one-minute warm-up. It does not keep measurement history in memory or interfere with the process. For comparison, leave only the aggregate skin active; separately test available and unavailable machines. Sustained Private Bytes growth matters more than a one-time working-set spike. All other skins and plugins in the same process also affect the measurement.

These changes remove unnecessary resource allocation in the configuration, but do not by themselves prove the absence of a leak in a particular Rainmeter/plugin version: a long measurement on a real installation is needed. If growth continues, save the CSV and Rainmeter version for further diagnosis.

## Build and checks

```powershell
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --onefile --console server_stats.py
# Result: dist/server_stats.exe

py -m unittest discover -s tests -v
```

Tests check the agent protocol, speed calculation, generation of different sizes, exclusion of disabled machines, offline handling, IPv6, validation, and UTF-16 INI. Visual rendering and real network connections must additionally be checked in Rainmeter with your VMs.
