# ServerStats — project description and context for moving monitoring to a website

> This document records the current project structure, the result of the joint improvements, and requirements for a future web section. It can be given to a developer or AI together with the source files.
>
> **Important:** the agent, Docker deployment, and Rainmeter widget are already implemented. The web section, central monitoring server, and history storage are **not implemented yet**. Sections with recommendations for the site are proposals, not descriptions of existing code.

## 1. What is in this folder

**ServerStats** is a small resource monitor for Windows and Linux machines, primarily virtual machines. The original task was to see the state of about **10–20 VMs** compactly on the desktop in the style of Win10 Widgets, without opening a separate window for each machine.

The project has two main parts:

1. **An agent on each monitored machine**: Python + Flask + psutil, serving current metrics over HTTP. Windows uses an EXE; Linux has a Docker setup.
2. **An aggregated Rainmeter widget**: polls the agents and shows one row per machine — hostname/IP, CPU, RAM, network, disk I/O, and disk usage.

The old single-machine skin is also retained. The new aggregated version does not replace it and does not require removing it.

The next task is to create a **section of the existing website with the same metrics, formatting, colors, and charts**. The website technology stack is not specified in this folder.

## 2. Current architecture

```text
Windows VM                          Linux VM
server_stats.exe                    Docker: server_stats.py + Gunicorn
        │ HTTP                              │ HTTP
        └────────────────┬──────────────────┘
                         │
                 Rainmeter on Windows
                 Aggregate-NN.ini
                         │
              rows, statuses, and charts

Widget configuration:
servers.json → generate.py → servers.inc + Aggregate*.ini
```

Key properties:

- The agent collects metrics from the local OS rather than querying a hypervisor API.
- Every VM must have its own reachable agent.
- `host_title` is a group/hypervisor label, **not a source of physical-host metrics**.
- There is no central database, queue, aggregation server, or long-term archive.
- The agent keeps only the latest snapshot; Rainmeter keeps a short chart history.
- The web version can reuse the agents' JSON API without parsing Rainmeter INI files.

## 3. File map

| Path | Purpose |
|---|---|
| `server_stats.py` | Metric collection, HTTP routes, JSON and text protocols, demo data |
| `server_stats.exe` | Windows binary in the root; correspondence to the exact source version must be checked |
| `dist/server_stats.exe` | Windows-agent build artifact |
| `requirements.txt` | Python-agent dependencies |
| `requirements-docker.txt` | Docker dependencies, including Gunicorn |
| `Dockerfile` | Python 3.13 slim Linux image, running Gunicorn as UID 65534 |
| `gunicorn.conf.py` | One worker, four HTTP threads, starts a separate collector after worker creation |
| `compose.yaml` | Two deployment modes: Docker Desktop and a real Linux host |
| `docker.env.example` | Example Docker environment variables |
| `.dockerignore` | Build-context exclusions |
| `ServerStats/ServerStats_Win10.ini` | Retained original single-machine skin |
| `ServerStats/@Resources/` | Rainmeter resources and styles |
| `ServerStats/@Resources/Aggregate/generate.py` | Generator for the common include and all aggregated-skin variants |
| `ServerStats/@Resources/Aggregate/servers.json` | Single editable machine list and widget settings |
| `ServerStats/@Resources/Aggregate/servers.inc` | Generated common variables; do not edit manually |
| `ServerStats/@Resources/Aggregate/servers.demo.json` | Example with four demo machines |
| `ServerStats/Aggregate/Aggregate.ini` | Automatic variant based on the number of enabled machines |
| `ServerStats/Aggregate/Aggregate-01.ini` … `Aggregate-20.ini` | Ready-made variants for 1–20 slots |
| `ServerStats/rebuild_aggregate.cmd` | Runs rebuilding through the Python Launcher `py.exe` |
| `tests/test_server_stats.py` | Agent, protocol, rate, and demo tests |
| `tests/test_aggregate.py` | Generator, layout, formatting, and state tests |
| `tests/test_docker.py` | Docker-configuration checks |
| `tests/monitor_rainmeter_memory.py` | Streaming Rainmeter memory-consumption diagnostics |
| `README.md` | Installation, configuration, and operation instructions |
| `PROJECT_CONTEXT.md` | This document: project description and guide for web implementation |

Generated INI and include files are written as UTF-16. JSON configuration is UTF-8. The generator does not require Flask or psutil.

## 4. Work completed during the improvements

### 4.1. From a single skin to a common VM dashboard

- The original single-machine skin was retained.
- An aggregated widget for multiple machines was created.
- **20 ready-made variants** were added, selectable in Rainmeter: 1 to 20 slots.
- An automatic variant for the full list was retained.
- All variants use **one `servers.json`**, rather than separate IP lists.
- Shared parameters were moved to generated `servers.inc`.
- Commands for generating, listing, adding, and removing machines were introduced.
- Scaling, polling-frequency configuration, and active-skin refresh were added.

### 4.2. List and layout

- Up to 10 slots use one panel.
- With 11–20 slots: VMs 1–10 are on the left, 11–20 on the right.
- Headers are repeated above both panels.
- Empty slots are labeled “not configured” and are not polled.
- Disabled entries are excluded from display and numbering.
- An N-slot variant polls only the first N enabled machines.
- All variants are in one Rainmeter configuration: choosing another variant replaces the previous one instead of starting a second set of polls.

### 4.3. Metrics and visual design

- Real hostname, disk usage, and disk reads/writes were added.
- CPU and RAM use lines with translucent fill and a border.
- Network uses two lines with one shared automatic scale.
- I/O uses a green chart of read plus write with automatic scaling.
- Disk usage uses a pie chart and used/total capacity.
- Gray numeric values and red warnings from 80% were added.
- Waiting, online/offline, and hiding unreliable stale values on error were added.
- Network was changed to adaptive Kbit/s, Mbit/s, and Gbit/s, rounded to one decimal place.
- Disk-read color matches network receive; disk-write color matches network send.

### 4.4. Final interface adjustments

After several iterations, the following appearance was agreed:

- Main numeric values have size **9** at scale 1.0.
- The hostname/IP column was narrowed to **140 px**.
- The network column was widened to **146 px**.
- Metric text and headers are centered relative to their corresponding charts.
- Hostname and address remain left-aligned.
- Disk I/O is on the left; the pie chart and capacity are on its right.
- Disk capacity is below the pie chart; its text field was widened to **130 px**.
- GB and MB/s units are next to current values, not in headers.
- RAM and disk-capacity values have spaces on both sides of `/`.
- There must be a space between `R`/`W` and the number.

**Do not restore concatenated `R0.0`/`W0.0` or remove spaces around `/`.**

### 4.5. Agent changes

- The metrics snapshot is updated atomically under a lock.
- Rates are calculated from differences in cumulative counters and monotonic time.
- Counter resets and invalid intervals are handled: rates never become negative.
- A JSON API and an extension of the old text protocol were added.
- Network precision was increased to six decimal places in Mbit/s.
- The text response prints network values as ordinary decimals, without exponent notation.
- Environment variables for address, port, filesystem, and Linux procfs were added.
- Safe synthetic demo routes 10/50/80/100 were added.

### 4.6. Docker

- A Linux image with Gunicorn was added.
- Real Linux host and Docker Desktop were separated, but kept in **one `compose.yaml`**.
- Startup without a profile was fixed: ordinary `docker compose up -d --build` starts the Desktop service.
- Linux uses an explicit `server-stats-linux` selection.
- Host networking, access to host metrics, a healthcheck, log limits, and privilege restrictions were added.
- It is documented that Docker Desktop does not replace the Windows agent and does not show Windows metrics.

### 4.7. Memory use and checks

- Native charts with width-limited history are used.
- Mass forced updates and redraws on every HTTP response were removed.
- Static-element geometry is not recreated on every update.
- Online/offline transitions are handled when state changes.
- Infrequent retries were introduced for unreachable VMs.
- Saving WebParser responses to the HTTP cache and cookie store was disabled.
- A separate tool for long-term Rainmeter memory measurement was added.
- Last completed set: **33 tests passed successfully**.

These measures reduce unnecessary allocations, but **the absence of a memory leak during a long Rainmeter run has not been proven**.

## 5. Final interface — guide for the website

### 5.1. Row composition

```text
HOSTNAME / IP       CPU            RAM                    NETWORK                    I/O                    DISK
vm-example          42%            3.2 / 8.0 GB (40%)     ↓12.3 ↑1.2 Mbit/s          R 0.0 W 0.0 MB/s       pie chart
192.168.1.11        [chart]        [chart]                [two lines]               [R + W chart]          128.0 / 256.0 GB
```

This is a relative-layout diagram, not a literal text table to implement.

### 5.2. Exact formats

| Metric | Example | Rule |
|---|---|---|
| CPU | `42%` | Whole-number percentage, chart 0–100% |
| RAM | `3.2 / 8.0 GB (40%)` | One decimal, whole-number percentage, spaces around `/` |
| Network | `↓12.3 ↑1.2 Mbit/s` | One line, one decimal place, one shared unit for both directions |
| Read/write | `R 0.0 W 0.0 MB/s` | Space after R and W, no `/` between directions, unit at the end |
| Disk capacity | `128.0 / 256.0 GB` | One decimal place, spaces around `/`, no separate percentage |

Do not replace `0.0` with an empty string or confuse a zero value with an unavailable machine.

**Units:** the GB label matches the agreed interface, but the agent divides memory and disk capacity by **1024³**. These are binary quantities, not decimal GB. For visual matching, do not silently recalculate them during migration. Disk MB/s, in contrast, is genuinely decimal: 1 MB = 1,000,000 bytes.

### 5.3. Colors

| Element | Value |
|---|---|
| Main background | `rgba(12, 12, 12, 250/255)` ≈ `#0C0C0C`, almost opaque |
| Ordinary numeric values | `rgb(178,178,178)` / `#B2B2B2` |
| CPU | `rgb(17,125,187)` / `#117DBB` |
| RAM | `rgb(139,18,174)` / `#8B12AE` |
| Network download, disk R | `rgb(237,165,130)` / `#EDA582` |
| Network upload, disk W | `rgb(100,200,255)` / `#64C8FF` |
| Disk, total I/O | `rgb(77,166,12)` / `#4DA60C` |
| Warning | `rgb(240,85,85)` / `#F05555` |
| Online | `rgb(100,200,125)` |
| Offline | `rgb(220,90,80)` |
| Waiting | `rgb(130,130,130)` |

Design: dark background, slight rounding, thin separators, Segoe UI, dense layout. The web version needs a readable CSS font size; Rainmeter `FontSize=9` must not be mechanically treated as 9 CSS px.

### 5.4. Warnings

- CPU **≥80%**: the number is red.
- RAM **≥80%**: the entire value, including the percentage, is red.
- Disk used space **≥80%**: capacity, pie chart, and R/W are red.
- The I/O chart remains green.
- When a value drops below 80%, its normal color returns.
- The threshold is applied to the original percentage, **before rounding for text**.
- Network has no warning threshold.

Important: in the current interface, red R/W means a **disk-usage warning**, not excessive speed or device-utilization percentage.

### 5.5. Charts and dimensions

- CPU and RAM: line + translucent fill + border; fixed 0–100% scale.
- Network: receive and send, two lines, shared automatic scale.
- I/O: one `read + write` series, green line with fill, automatic scale.
- Capacity: pie chart based on `disk_percent`.
- All line charts in the current widget are **36 px** high.
- Row height: **88 px**; width of one panel: **828 px**.
- Gap between panels: **16 px**.
- 10 slots: approximately **828 × 952 px**; 11–20 slots: **1672 × 952 px** at scale=1.

For the website, preserve hierarchy and relative placement but use responsive layout: on a narrow screen, do not compress the whole dashboard until it is unreadable.

### 5.6. Adaptive network units

The agent's raw values are always in **Mbit/s**.

```text
peak = max(net_recv_mbps, net_sent_mbps)

peak < 1:       display Kbit/s, multiply raw values by 1000
1 ≤ peak < 1000: display Mbit/s, leave raw values unchanged
peak ≥ 1000:    display Gbit/s, divide raw values by 1000
```

Both directions use the same selected unit. After conversion, round to one decimal place and retain one digit in the string. At zero, use Kbit/s. When speed decreases, switch units back.

**Store chart history in raw Mbit/s.** Changing the displayed unit must not change the scale of already stored points relative to new ones.

## 6. Agent and API — ready foundation for the website

### 6.1. Routes

| URL | Format | Purpose |
|---|---|---|
| `GET /stats` | Text | Existing Rainmeter protocol |
| `GET /api/stats` | JSON | Current real metrics; use this for the website |
| `GET /demo/10`, `/demo/50`, `/demo/80`, `/demo/100` | Text | Synthetic metrics for Rainmeter |
| `GET /api/demo/10`, `/api/demo/50`, `/api/demo/80`, `/api/demo/100` | JSON | Synthetic metrics for the website |

Default port: **5000**; bind address: `0.0.0.0`.

### 6.2. JSON example

```json
{
  "cpu": 42.0,
  "ram_percent": 40.0,
  "ram_used_gb": 3.2,
  "ram_total_gb": 8.0,
  "net_recv_mbps": 12.3,
  "net_sent_mbps": 1.2,
  "hostname": "vm-example",
  "disk_percent": 50.0,
  "disk_used_gb": 128.0,
  "disk_total_gb": 256.0,
  "disk_read_mbps": 0.0,
  "disk_write_mbps": 0.0
}
```

This illustrates the contract; it is not saved data from a particular machine.

### 6.3. Fields and meaning

| Field | Unit | Use |
|---|---|---|
| `cpu` | % | Overall load of all CPUs, number and chart |
| `ram_percent` | % | psutil percentage, warning and chart |
| `ram_used_gb` | bytes / 1024³ | Used memory, rounded to one decimal |
| `ram_total_gb` | bytes / 1024³ | Total memory, rounded to one decimal |
| `net_recv_mbps` | Mbit/s | Receive rate, up to six decimal places |
| `net_sent_mbps` | Mbit/s | Send rate, up to six decimal places |
| `hostname` | string | OS name, not the connection address |
| `disk_percent` | % | Usage of the selected filesystem |
| `disk_used_gb` | bytes / 1024³ | Used capacity, rounded to one decimal |
| `disk_total_gb` | bytes / 1024³ | Total capacity, rounded to one decimal |
| `disk_read_mbps` | **MB/s** | Reads, one decimal; despite the `mbps` suffix, these are megabytes |
| `disk_write_mbps` | **MB/s** | Writes, one decimal; despite the `mbps` suffix, these are megabytes |

Do not divide disk rates by 8 or interpret them as Mbit/s. Total disk chart = `disk_read_mbps + disk_write_mbps`.

Take `ram_percent` from the API instead of recalculating it from rounded capacities: the semantics of `mem.used` and `mem.percent` can differ across operating systems.

### 6.4. How data is collected

- A separate daemon thread collects data approximately once per second.
- An HTTP request reads a ready snapshot copy under a lock; it does not start another expensive collection.
- Rate timing uses `time.monotonic()`.
- Network: byte difference ×8 / 1,000,000 / actual elapsed seconds.
- Disks: byte difference / 1,000,000 / actual elapsed seconds.
- If a counter reset or the interval is non-positive, return 0 rather than a negative rate.
- Network is summed over interfaces returned by psutil, with no separate interface selection. This is not guaranteed to be traffic from one external NIC; virtual interfaces can affect the total.
- I/O is summed over disk devices returned by psutil. It is not I/O for one mount point and is not `% disk busy`.
- `SERVER_STATS_DISK` selects only the filesystem used for capacity, not the device set used for I/O.

### 6.5. Current API limitations

- No last-successful-collection time, snapshot sequence number, or schema version.
- No history, authentication, TLS, WebSocket/SSE, CORS configuration, or machine management.
- No VM identifier in the snapshot: take `id` from the machine registry; do not substitute hostname.
- Numeric fields may be zero at startup until the first collection.
- After a handled collector error, the previous snapshot remains. Therefore **HTTP 200 does not prove that metrics are fresh**.
- On a disk-capacity read error, zeros are returned: the current API cannot distinguish that from real zero values with a separate flag.
- No uptime, temperature, processes, SMART, latency, partition list, or interface list.

For complete web monitoring, extend the API with freshness and validity metadata while preserving existing fields and `/stats` compatibility.

### 6.6. Old text protocol

The field order is fixed:

```text
CPU;RAM;RAM_USED;RAM_TOTAL;NET_RECV;NET_SENT;HOSTNAME;DISK_PERCENT;DISK_USED;DISK_TOTAL;DISK_READ;DISK_WRITE
```

Each item has the form `KEY:value`, with items separated by `;`. The first six fields are retained for the old client. The new aggregated Rainmeter skin needs all extended fields. Do not use this protocol for the website: JSON is simpler and more reliable.

## 7. Machine-list configuration

Example common Rainmeter configuration:

```json
{
  "host_title": "PVE-01",
  "scale": 1.0,
  "update_seconds": 2,
  "servers": [
    {
      "id": "db01",
      "address": "192.168.1.11",
      "port": 5000,
      "name": "db-01",
      "enabled": true
    },
    {
      "id": "demo80",
      "address": "127.0.0.1",
      "port": 5000,
      "name": "DEMO-80",
      "enabled": true,
      "demo_load": 80
    }
  ]
}
```

- `id`: unique stable key, using Latin letters/digits/`_`/`-`.
- `address`: IPv4, IPv6, or DNS name.
- `port`: 1–65535, default 5000.
- `name`: fallback label; the real hostname comes from the agent.
- `enabled`: display/poll, or temporarily exclude.
- `demo_load`: `10`, `50`, `80`, `100`; absent or `null` means real data.
- Array order controls display order.
- `update_seconds`: 1–3600, usually 2 seconds.
- `scale`: 0.6–2.0; a Rainmeter parameter, not a ready-made CSS scale for the website.

The website can import this list, but should store it on the backend. There is currently no automatic synchronization between the website and JSON.

Generator commands from the project root:

```powershell
py ServerStats/@Resources/Aggregate/generate.py
py ServerStats/@Resources/Aggregate/generate.py list
py ServerStats/@Resources/Aggregate/generate.py --refresh add 192.168.1.25 --id vm25 --name vm-25
py ServerStats/@Resources/Aggregate/generate.py --refresh remove vm25
```

**Do not overwrite an installed user's `servers.json` when updating the project.** Make appearance changes in `generate.py`, then regenerate the INI files.

## 8. Running and deploying agents

### 8.1. Windows

For development:

```powershell
py -m pip install -r requirements.txt
py server_stats.py
```

The EXE is used for VMs. Build:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --onefile --console server_stats.py
# Result: dist/server_stats.exe
```

Environment variables:

| Variable | Purpose |
|---|---|
| `SERVER_STATS_HOST` | Listen address, default 0.0.0.0 |
| `SERVER_STATS_PORT` | Port, default 5000 |
| `SERVER_STATS_DISK` | Path whose capacity is measured; system root by default |
| `SERVER_STATS_PROCFS` | Linux procfs path; not needed for a normal Windows EXE |

Example:

```powershell
$env:SERVER_STATS_DISK = 'D:\'
$env:SERVER_STATS_PORT = '5000'
.\server_stats.exe
```

The Windows EXE uses the built-in Flask server. Automatic Windows-service installation is not implemented.

**Artifact history:** during development, the root EXE was held by a running process and therefore could not always be replaced. Earlier README text mentioned `server_stats_updated.exe`; at the time this document was prepared, that file did not exist in the root. The root EXE and `dist/server_stats.exe` are available. Do not consider a binary current based only on its name: check `/api/stats`, the demo route, and rebuild from the current source if necessary. Do not stop a running EXE automatically.

### 8.2. Linux VM — real VM metrics

```bash
docker compose up -d --build server-stats-linux
curl http://127.0.0.1:5000/api/stats
```

- `network_mode: host` — the VM's network.
- `uts: host` — the VM's hostname.
- `/proc` → `/host/proc`, `/sys` → `/sys`, `/` → `/host/root`, read-only.
- psutil is pointed at `/host/proc`.
- By default, capacity is measured for `/host/root`.
- For host `/data`, set `SERVER_STATS_DISK=/host/root/data`.
- Rootless Docker is not supported for this host-monitoring setup.

Gunicorn starts one worker with four request-processing threads; the collector starts in `post_worker_init`. Simply increasing workers creates separate snapshots and collectors and requires architectural review.

Container: UID 65534, read-only root filesystem, `cap_drop: ALL`, `no-new-privileges`, tmpfs for `/tmp`, healthcheck, 5 MB ×2 log limit, `restart: unless-stopped`. The healthcheck tests API availability and basic values, **not snapshot freshness**. `unhealthy` alone does not imply an automatic restart.

Bind-mounting system directories, especially the host root, is deliberate read access to data available to this UID. It is not complete isolation from the host.

### 8.3. Docker Desktop on Windows — verification mode only

```powershell
docker compose up -d --build
curl.exe http://127.0.0.1:5000/api/stats
```

The `server-stats` service uses bridge networking and publishes the port by default at `127.0.0.1:5000`.

**It shows the Docker Desktop Linux environment, not Windows. The EXE is required for Windows metrics.**

Do not run both Compose services at once. Select the Linux service explicitly; `COMPOSE_PROFILES=linux` together with ordinary `up` may select both.

During development, one Docker rebuild attempt did not finish because the Docker Desktop daemon was unavailable. Configuration tests do not prove that the latest image successfully runs on a real VM.

## 9. Demo mode

Demo is **not a stress test**. The routes create no real load and do not alter live metrics.

For state N of 10/50/80/100:

- hostname = `DEMO-N`;
- CPU, RAM, and disk usage = N%;
- total memory = 16 binary GB, N% used;
- total disk = 256 binary GB, N% used;
- network in each direction = N Mbit/s;
- reads and writes = N MB/s each, total I/O = 2N MB/s.

An unknown demo state returns 404. One agent can serve all four demo rows. Use them to check normal colors and the red warning at 80/100. Values are constant, so the chart becomes horizontal after history fills.

For the website, use `/api/demo/N` JSON routes and always show a DEMO marker. Testing changing load and network-unit switching requires separate test sequences; the current four demo routes do not generate them.

## 10. Memory and stability

Native Rainmeter charts store a fixed number of points based on width, not an infinite array. Static meters use `UpdateDivider=-1`, automatic window-size recalculation is disabled, and use of DynamicVariables is reduced.

The HTTP callback changes only the online variable. A separate measure handles state transitions, switching visibility and retry intervals. There is no `!UpdateMeter *`/`!Redraw` on every response, status-Shape recreation, automatic restart, or forced memory trimming.

WebParser: `ForceReload | NoCacheWrite | NoCookies`, without a proxy. After an error, the retry interval is `max(30, update_seconds)`; after success, it is normal.

Measurement:

```powershell
py tests/monitor_rainmeter_memory.py --minutes 60 --csv rainmeter-memory.csv
```

The tool writes Private Bytes, working set, and handles to CSV, does not accumulate the full history in memory, and does not interfere with the process. Evaluate the long-term Private Bytes trend, preferably with other skins disabled.

Use the same principle for the website: a bounded point buffer, release chart resources, and no new timers or subscriptions on every render. A forced page reload is not a leak fix.

## 11. Proposed web-section architecture — not implemented yet

### 11.1. Recommended design

```text
VM agents: GET /api/stats
           │
           ▼
Website backend / shared collector
- trusted machine registry
- bounded concurrency and timeouts
- schema validation, statuses, and receipt time
- latest snapshot + bounded history
           │
           ▼
Authorized website API
           │ HTTP polling / SSE / WebSocket
           ▼
Web dashboard: rows, statuses, charts
```

The backend polls each VM **once per interval regardless of the number of open browsers**. Users receive the shared result. Do not attach a separate collector to every page HTTP request.

Why not request agents directly from browsers:

- The agent has no CORS configuration.
- An HTTPS page must not access HTTP agents through mixed content.
- Users may not have access to the VM network.
- Internal infrastructure addresses should not be exposed publicly.
- Each browser would multiply requests to VMs.
- Centralized authorization and access limits are easier.

Do not solve this by publishing every agent to the internet or allowing CORS `*`.

### 11.2. What to reuse

**Use without changing the visual logic:**

- `/api/stats` and `/api/demo/N`;
- metric composition, units, and rounding rules;
- the 80% warning threshold;
- adaptive network units;
- final strings with spaces;
- colors, chart composition, and separation of I/O from disk capacity;
- the machine registry imported from `servers.json`.

**Do not port literally:**

- Rainmeter INI, WebParser, bangs, and UTF-16 — these are Rainmeter-client specifics;
- 20 size-specific files — one responsive component is enough on the website;
- `scale` — use CSS and responsive layout instead;
- missing freshness metadata — the website needs this improved;
- history stored only in the chart component, if history must survive reloads.

### 11.3. Proposed website-backend contract

Example of a **new designed response, not an existing one**:

```json
{
  "group_id": "pve01",
  "title": "PVE-01",
  "poll_interval_seconds": 2,
  "servers": [
    {
      "id": "db01",
      "name": "db-01",
      "address": "192.168.1.11",
      "status": "online",
      "last_received_at": "2026-01-01T12:00:00Z",
      "last_error": null,
      "metrics": {
        "cpu": 42.0,
        "ram_percent": 40.0,
        "ram_used_gb": 3.2,
        "ram_total_gb": 8.0,
        "net_recv_mbps": 12.3,
        "net_sent_mbps": 1.2,
        "hostname": "db-01",
        "disk_percent": 50.0,
        "disk_used_gb": 128.0,
        "disk_total_gb": 256.0,
        "disk_read_mbps": 0.0,
        "disk_write_mbps": 0.0
      }
    }
  ]
}
```

`last_received_at` is the time the backend successfully received the response, **not the agent's collection time**. To reliably check collection freshness, add a timestamp/sequence and collector state to the agent separately. All dates in examples are illustrative.

Suggested states:

- `waiting`: no successful response yet;
- `online`: a valid, checked response was received;
- `offline`: timeout, network failure, or request error;
- `incompatible`: required fields are missing or types are wrong;
- `stale`: the snapshot was received long ago or the agent reported stale collection;
- `disabled`: the administrator disabled the machine for monitoring.

This extends the three indicators in the current widget. For offline/stale, do not show old values as fresh. A last-known snapshot is acceptable only with an explicit marker and timestamp.

### 11.4. Polling and history

Initial recommendations:

- Agent collection: the existing interval of about 1 second.
- Backend polling: usually 2 seconds, as in the widget.
- Explicit network timeout and concurrency limit.
- Avoid overlapping requests to one machine unless necessary.
- One VM's failure must not block the others.
- Increase retry intervals after errors; the current widget's guide is 30 seconds.
- Keep a ring buffer, for example 120–300 points per machine.
- Timestamps are mandatory: do not assume point spacing is always equal.
- On connection loss, insert a gap/null rather than an artificial zero.
- Zero speed from an available agent is a valid measurement.
- If a snapshot timestamp/sequence is added later, use it to detect duplicates.

Store raw numeric values and format them for display. In particular, do not store strings such as `12.3 Mbit/s` in history.

For hours/days of history: use separate storage, retention, aggregation of old points, and a query-range limit. The current project has none of these. Do not create infinite arrays in the browser or backend memory.

### 11.5. Interface components

Possible decomposition, regardless of framework:

```text
MonitoringPage
  GroupHeader
  ColumnHeaders
  ServerRow
    ServerIdentity + StatusIndicator
    CpuMetric + PercentChart
    RamMetric + PercentChart
    NetworkMetric + DualNetworkChart
    DiskIOMetric + ThroughputChart
    DiskCapacityMetric + PieChart
```

Common utilities: capacity formatting, network formatting, I/O formatting, threshold checking, response normalization, and bounded history buffering.

Provide for:

- configuration-order sorting as the original order;
- enabling/disabling and adding/removing machines only with appropriate permissions;
- tooltips with full hostname, update time, and exact values;
- DEMO marking;
- chart gaps when unavailable;
- no duplicate timers when switching tabs/routes;
- correct removal of charts and subscriptions on unmount;
- readable mobile adaptation;
- text status in addition to the colored dot.

### 11.6. Security

The current agent has **no authentication or TLS**. Allow the port only to a trusted collector/Rainmeter through LAN/VPN and firewall. The agent is not intended for direct internet access.

For the website:

- authorize viewing infrastructure metrics;
- restrict registry editing separately;
- browser communicates with the website backend over HTTPS;
- use a private network/VPN or improved secure transport between backend and agents;
- do not accept an arbitrary user-supplied URL for server-side fetches;
- validate addresses/ports against an allowlisted registry or networks, and protect against SSRF, redirects, and DNS rebinding;
- render hostnames and other strings as text, never inject them into HTML;
- validate metric types, finiteness, and allowed ranges;
- limit response size, timeouts, and concurrent connections;
- do not return secrets or raw internal stack traces to clients;
- protect state-changing cookie-session requests against CSRF.

The current Rainmeter-configuration validation is not a ready SSRF defense for a web backend.

## 12. Checks and web-migration readiness criteria

### Existing tests

```powershell
py -m unittest discover -s tests -q
```

At the time of the latest changes: **33 tests passed**. They check the agent, protocol, rate calculation, demos, configuration, size generation, positioning, units, string formats, warnings, and Docker settings. They are not browser end-to-end tests and do not guarantee that a real Docker daemon works.

### Additional website checks

1. Windows EXE and Linux Docker provide the required JSON schema.
2. With 1, 10, 11, and 20 machines, the layout remains readable.
3. Exact formats are preserved:
   - `R 0.0 W 0.0 MB/s`;
   - `3.2 / 8.0 GB (40%)`;
   - `128.0 / 256.0 GB`.
4. Text and headers are centered relative to charts; hostname/IP is on the left.
5. The 80% threshold activates and clears; 79.9 is not treated as 80 solely because of display rounding.
6. Disk capacity and disk throughput are not mixed.
7. Network units are correct around 1 and 1000 Mbit/s, at zero, and when switching back.
8. The network chart is not distorted when units change.
9. Offline/incompatible states do not look like real zero and do not leave stale numbers appearing “live”.
10. One unreachable agent does not delay the whole dashboard.
11. Multiple open users do not multiply polling of every VM.
12. History is bounded; memory does not grow indefinitely over several hours.
13. DEMO-10/50/80/100 are clearly marked and provide expected values.
14. Narrow/mobile layout, long hostnames, large capacities, and high speeds are checked without text clipping.
15. Access and editing are permission-limited; SSRF and XSS are blocked.

## 13. Brief assignment for the next developer

> Integrate a monitoring section into the existing website, modeled on the ServerStats Rainmeter monitor for Windows and Linux VMs. The agent already exists in `server_stats.py`: real metrics are at `/api/stats`, demos at `/api/demo/{10,50,80,100}`. The row consists of hostname/IP with status, CPU with chart, RAM with chart, network receive/send with a two-line chart, R/W with a total chart, and disk usage on the right with a pie chart and capacity beneath it. Preserve colors, the 80% warning, adaptive network units, and the agreed spaces. Exact examples: `R 0.0 W 0.0 MB/s`, `3.2 / 8.0 GB (40%)`, `128.0 / 256.0 GB`. Center values relative to charts; keep hostname/IP left-aligned. The website backend must centrally poll a trusted agent registry, validate responses, and provide the shared result to browsers. Do not expose agents to the internet or make direct browser requests to internal IPs. Bound history and do not replace unavailability with zeros. The current API does not report collection time — do not confuse HTTP availability with metric freshness. The web part is not yet present in this folder; first study the target site's stack and integrate with its authorization, API, and design system.
