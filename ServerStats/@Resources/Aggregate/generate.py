"""Generate a compact two-column Rainmeter dashboard from servers.json (Python 3.9+)."""
import argparse
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

RESOURCE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = RESOURCE_DIR / "servers.json"
SKIN_PATH = RESOURCE_DIR.parent.parent / "Aggregate" / "Aggregate.ini"


def safe_text(value, field):
    value = str(value).strip()
    # Rainmeter interprets brackets, hashes and quotes even inside Text options.
    if not value or any(c in value for c in '\r\n[]#;"'):
        raise ValueError(f"{field}: empty text or Rainmeter control characters")
    return value


def validate(config):
    safe_text(config.get("host_title", "VIRTUAL MACHINES"), "host_title")
    scale = float(config.get("scale", 1))
    interval = int(config.get("update_seconds", 2))
    if not math.isfinite(scale) or not 0.6 <= scale <= 2:
        raise ValueError("scale must be between 0.6 and 2")
    if not 1 <= interval <= 3600:
        raise ValueError("update_seconds must be between 1 and 3600")
    if not isinstance(config.get("servers"), list):
        raise ValueError("servers must be a list")
    ids = set()
    for server in config["servers"]:
        sid = server.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in ids:
            raise ValueError(f"Invalid or duplicate server id: {sid}")
        ids.add(sid)
        address = server.get("address", "")
        try:
            ipaddress.ip_address(address)
        except ValueError:
            if len(address) > 253 or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", address):
                raise ValueError(f"Invalid IP / DNS address: {address}")
        if not 1 <= int(server.get("port", 5000)) <= 65535:
            raise ValueError(f"Invalid port: {sid}")
        if "name" in server and server["name"]:
            safe_text(server["name"], "name")
        demo = server.get("demo_load")
        if demo is not None and (type(demo) is not int or demo not in (10, 50, 80, 100)):
            raise ValueError(f"demo_load must be 10, 50, 80 or 100: {sid}")
        if not isinstance(server.get("enabled", True), bool):
            raise ValueError(f"enabled must be true or false: {sid}")
    return config


def stats_path(server):
    return "stats" if server.get("demo_load") is None else f"demo/{server['demo_load']}"


def render(config, slots=None, shared=False):
    validate(config)
    servers = [s for s in config["servers"] if s.get("enabled", True)]
    if slots is not None:
        if not 1 <= slots <= 20:
            raise ValueError("slots must be between 1 and 20")
        servers = servers[:slots]
    configured = len(servers)
    row_count = configured if slots is None else slots
    scale = float(config.get("scale", 1))
    interval = int(config.get("update_seconds", 2))

    # 10 cards x 100 px = 1000 px: fits Full HD vertically. At 1.0 scale,
    # two 820 px columns and a 16 px gutter occupy 1656 / 1920 px.
    card_width, card_height = 820, 100
    column_gap = 16
    column_stride = card_width + column_gap
    columns = 2 if row_count > 10 else 1
    row_count_per_column = (max(10, row_count - 10) if columns == 2 else row_count)
    canvas_width = card_width + (columns - 1) * column_stride
    canvas_height = max(1, row_count_per_column) * card_height

    def px(value):
        return str(max(1, round(value * scale))) if value else "0"

    def top(index):
        return ((index - 1) if index <= 10 else (index - 11)) * card_height

    lines = []

    def section(name, **options):
        match = re.match(r"VM(\d+)", name)
        # All shapes use local coordinates, so their meter X can be
        # shifted just like graph and String meters.
        if "Meter" in options and match and int(match.group(1)) > 10:
            options["X"] = str(int(options.get("X", 0)) + int(px(column_stride)))
        lines.append(f"[{name}]")
        lines.extend(f"{key}={value}" for key, value in options.items())
        lines.append("")

    def text(name, label, x, y, width, **opts):
        height = opts.pop("height", 27)
        alignment = opts.get("StringAlign")
        if alignment in ("Center", "CenterCenter"):
            x += width / 2  # Rainmeter text X is the center anchor.
        if alignment == "CenterCenter":
            y += height / 2  # Center the text vertically as well.
        section(name, Meter="String", MeterStyle="TextStyle", Text=label,
                X=px(x), Y=px(y), W=px(width), H=px(height), **opts)

    def shape(name, x, y, definition, **opts):
        section(name, Meter="Shape", X=px(x), Y=px(y), Shape=definition,
                UpdateDivider=-1, **opts)

    def data(prefix, name, label, x, y, width, **opts):
        text(prefix + name, label, x, y, width, Group=prefix + "Data",
             Hidden=1, UpdateDivider=interval, DynamicVariables=1, **opts)

    section("Rainmeter", Update=1000, AccurateText=1, DynamicWindowSize=0,
            ContextTitle="Open VM list",
            ContextAction='["notepad.exe" "#@#Aggregate\\servers.json"]',
            ContextTitle2="Rebuild and refresh",
            ContextAction2='["py.exe" "#@#Aggregate\\generate.py" "--refresh"]')
    section("Metadata", Name="ServerStats Aggregate" + (f" {slots:02d} VM" if slots else ""),
            Information="Compact navy dashboard. Configure @Resources/Aggregate/servers.json",
            Version="2.0")
    colors = dict(
        BackgroundColor="10,14,32,252",
        BorderColor="84,74,137,205",
        TextColor="236,238,255",
        MutedColor="168,175,204",
        SubtleColor="128,138,169",
        CPUColor="57,189,255",
        CPUFrameColor="31,99,139",
        RAMColor="190,127,243",
        RAMFrameColor="99,70,135",
        NetColor="255,153,65",
        NetFrameColor="143,75,30",
        UploadColor="50,191,251",
        DiskColor="169,247,0",
        DiskFrameColor="68,117,20",
        PieColor="112,190,0",
        WarningColor="240,88,96",
    )
    if shared:
        colors["@Include"] = "#@#Aggregate\\servers.inc"
    colors.update({f"VM{i}Online": -1 for i in range(1, configured + 1)})
    colors.update({f"VM{i}NetUnit": "Кбит/с" for i in range(1, configured + 1)})
    section("Variables", **colors)
    section("TextStyle", FontFace="Segoe UI", FontSize=px(10), FontColor="#TextColor#",
            AntiAlias=1, ClipString=1, DynamicVariables=0, UpdateDivider=-1)
    # A transparent fixed canvas anchors every row and both columns.
    shape("Background", 0, 0,
          f"Rectangle 0,0,{px(canvas_width)},{px(canvas_height)} | Fill Color 0,0,0,1 | StrokeWidth 0")

    number = r"([0-9]+(?:\.[0-9]+)?)"
    regexp = ("(?s)^CPU:" + number + ";RAM:" + number + ";RAM_USED:" + number
              + ";RAM_TOTAL:" + number + ";NET_RECV:" + number + ";NET_SENT:" + number
              + ";HOSTNAME:([^;\\r\\n]+);DISK_PERCENT:" + number
              + ";DISK_USED:" + number + ";DISK_TOTAL:" + number
              + ";DISK_READ:" + number + ";DISK_WRITE:" + number + "(?:;|$)")

    def graph_frame(prefix, suffix, x, y, frame_color):
        # Plots reduced by ~20%, centered in each unchanged metric column.
        shape(prefix + suffix + "Frame", x, y,
              f"Rectangle 0,0,{px(110)},{px(38)},5 | "
              f"Fill Color 14,20,37,224 | Stroke Color #{frame_color}# | StrokeWidth 1",
              Group=prefix + "Data", Hidden=1)
        shape(prefix + suffix + "Baseline", x + 4, y + 35,
              f"Line 0,0,{px(103)},0 | Stroke Color 120,132,161,32 | StrokeWidth 1",
              Group=prefix + "Data", Hidden=1)

    def graph(prefix, suffix, measure, x, y, color, *, secondary=None, autoscale=0, fill=True):
        common = dict(X=px(x + 4), Y=px(y + 3), W=px(103), H=px(32),
                      MeasureName=prefix + measure, AutoScale=autoscale, AntiAlias=1,
                      UpdateDivider=interval, Group=prefix + "Data", Hidden=1)
        if fill and secondary is None:
            section(prefix + suffix + "Fill", Meter="Histogram",
                    PrimaryColor=f"#{color}#,27", **common)
        params = dict(Meter="Line", LineCount=2 if secondary else 1,
                      LineColor=f"#{color}#", LineWidth=1, DynamicVariables=1,
                      **common)
        if secondary:
            params["MeasureName2"] = prefix + secondary
            params["LineColor2"] = "#UploadColor#"
        section(prefix + suffix, **params)

    for i, server in enumerate(servers, 1):
        p = f"VM{i}"
        y = top(i)
        group = p + "Data"
        friendly_name = f"#{p}Name#" if shared else (server.get("name") or server["id"])
        address = f"#{p}Address#" if shared else server["address"]
        urlhost = f"[{server['address']}]" if ":" in server["address"] else server["address"]
        endpoint = ("http://#" + p + "URLHost#:#" + p + "Port#/#" + p + "StatsPath#"
                    if shared else
                    f"http://{urlhost}:{int(server.get('port', 5000))}/"
                    + ("stats" if server.get("demo_load") is None else f"demo/{server['demo_load']}"))

        # Full-HD card: four framed charts, live values, and the disk ring.
        shape(p + "Card", 1, y + 1,
              f"Rectangle 0,0,{px(card_width - 2)},{px(card_height - 2)},12 | "
              "Fill Color #BackgroundColor# | Stroke Color #BorderColor# | "
              "StrokeWidth 1")
        section(p + "Source", Measure="WebParser", URL=endpoint, RegExp=regexp,
                UpdateRate=interval, Flags="ForceReload | NoCacheWrite | NoCookies",
                ProxyServer="/none", FinishAction=f"[!SetVariable {p}Online 1]",
                OnConnectErrorAction=f"[!SetVariable {p}Online 0]",
                OnRegExpErrorAction=f"[!SetVariable {p}Online 0]",
                OnDownloadErrorAction=f"[!SetVariable {p}Online 0]")
        success = (
            f"[!ShowMeterGroup {group}][!HideMeter {p}Offline][!HideMeter {p}Waiting]"
            f"[!HideMeter {p}Address][!HideMeter {p}DotWaiting]"
            f"[!HideMeter {p}DotOffline][!ShowMeter {p}DotOnline]"
            f'[!SetOption {p}Source UpdateRate {interval}]')
        failure = (
            f"[!HideMeterGroup {group}][!ShowMeter {p}Offline][!HideMeter {p}Waiting]"
            f"[!ShowMeter {p}Address][!HideMeter {p}DotWaiting]"
            f"[!HideMeter {p}DotOnline][!ShowMeter {p}DotOffline]"
            f'[!SetOption {p}Source UpdateRate {max(30, interval)}]')
        section(p + "Connection", Measure="Calc", Formula=f"#{p}Online#",
                DynamicVariables=1, IfCondition=f"({p}Connection = 1)",
                IfTrueAction=success, IfCondition2=f"({p}Connection = 0)",
                IfTrueAction2=failure)
        fields = ["CPU", "RAM", "RAMUsed", "RAMTotal", "Recv", "Sent",
                  "Hostname", "Disk", "DiskUsed", "DiskTotal", "DiskRead", "DiskWrite"]
        for index, field in enumerate(fields, 1):
            options = dict(Measure="WebParser", URL=f"[{p}Source]", StringIndex=index)
            if field in ("CPU", "RAM", "Disk"):
                options.update(MinValue=0, MaxValue=100)
            if field == "Hostname":
                options["Substitute"] = '""' + ":" + '"' + friendly_name + '"'
            section(p + field, **options)

        section(p + "NetPeak", Measure="Calc", Formula=f"Max({p}Recv, {p}Sent)",
                MinValue=0)
        section(p + "NetScale", Measure="Calc",
                Formula=f"({p}NetPeak >= 1000 ? 1000 : ({p}NetPeak >= 1 ? 1 : 0.001))",
                IfCondition=f"({p}NetScale = 0.001)",
                IfTrueAction=f'[!SetVariable {p}NetUnit "Кбит/с"]',
                IfCondition2=f"({p}NetScale = 1)",
                IfTrueAction2=f'[!SetVariable {p}NetUnit "Мбит/с"]',
                IfCondition3=f"({p}NetScale = 1000)",
                IfTrueAction3=f'[!SetVariable {p}NetUnit "Гбит/с"]')
        for direction in ("Recv", "Sent"):
            section(p + "Net" + direction + "Display", Measure="Calc",
                    Formula=f"Round({p}{direction} / {p}NetScale, 1)",
                    MinValue=0, NumOfDecimals=1)
        section(p + "DiskTotalIO", Measure="Calc",
                Formula=f"{p}DiskRead + {p}DiskWrite", MinValue=0)
        section(p + "DiskTrack", Measure="Calc", Formula="100",
                MinValue=0, MaxValue=100)

        for state, color in (("Waiting", "129,138,163"),
                             ("Online", "52,224,122"), ("Offline", "239,91,94")):
            shape(p + "Dot" + state, 14, y + 15,
                  f"Ellipse {px(4)},{px(4)},{px(4)} | "
                  f"Fill Color {color} | StrokeWidth 0",
                  Hidden=0 if state == "Waiting" else 1)

        text(p + "Name", friendly_name, 28, y + 7, 148,
             FontSize=px(11), FontColor="#TextColor#", StringStyle="Bold", height=17)
        text(p + "Address", address, 28, y + 33, 148,
             FontSize=px(10), FontColor="#MutedColor#", height=17)
        data(p, "HostnameText", "%1", 28, y + 33, 148,
             MeasureName=p + "Hostname", FontSize=px(10),
             FontColor="#MutedColor#", height=17)
        text(p + "Waiting", "Подключение...", 28, y + 63, 148,
             FontSize=px(9), FontColor="#SubtleColor#", height=15)
        text(p + "Offline", "Нет соединения", 28, y + 63, 148,
             FontSize=px(9), FontColor="#WarningColor#", Hidden=1, height=15)
        data(p, "Status", f"Онлайн · интервал {interval} с",
             28, y + 63, 148, FontSize=px(9),
             FontColor="#SubtleColor#", height=15)

        # LeftBottom anchors each line to its actual text bottom, 2 px above the plot.
        data(p, "CPUValue", "%1%", 199, y + 47, 110,
             MeasureName=p + "CPU", NumOfDecimals=1,
             FontSize=px(8), FontColor="#CPUColor#", StringStyle="Bold",
             StringAlign="LeftBottom", height=17)
        data(p, "RAMValue", f"%1 / %2 ГБ ([{p}RAM:0]%)", 325, y + 47, 110,
             MeasureName=p + "RAMUsed", MeasureName2=p + "RAMTotal",
             NumOfDecimals=1, FontSize=px(8), FontColor="#RAMColor#",
             StringAlign="LeftBottom", height=17)
        data(p, "NetValue", f"↓ %1 #{p}NetUnit#", 451, y + 29, 110,
             MeasureName=p + "NetRecvDisplay", NumOfDecimals=1,
             FontSize=px(8), FontColor="#NetColor#", StringAlign="LeftBottom", height=15)
        data(p, "NetUpload", f"↑ %1 #{p}NetUnit#", 451, y + 47, 110,
             MeasureName=p + "NetSentDisplay", NumOfDecimals=1,
             FontSize=px(8), FontColor="#UploadColor#", StringAlign="LeftBottom", height=15)
        data(p, "DiskIO", "R %1 MB/s", 577, y + 29, 110,
             MeasureName=p + "DiskRead", NumOfDecimals=2,
             FontSize=px(8), FontColor="#DiskColor#", StringAlign="LeftBottom", height=15)
        data(p, "DiskWriteValue", "W %1 MB/s", 577, y + 47, 110,
             MeasureName=p + "DiskWrite", NumOfDecimals=2,
             FontSize=px(8), FontColor="#UploadColor#", StringAlign="LeftBottom", height=15)

        for suffix, x, color in (("CPUGraph", 199, "CPUFrameColor"),
                                 ("RAMGraph", 325, "RAMFrameColor"),
                                 ("NetGraph", 451, "NetFrameColor"),
                                 ("DiskIOGraph", 577, "DiskFrameColor")):
            graph_frame(p, suffix, x, y + 49, color)
        graph(p, "CPUGraph", "CPU", 199, y + 49, "CPUColor")
        graph(p, "RAMGraph", "RAM", 325, y + 49, "RAMColor")
        graph(p, "NetGraph", "Recv", 451, y + 49, "NetColor",
              secondary="Sent", autoscale=1, fill=False)
        graph(p, "DiskIOGraph", "DiskRead", 577, y + 49, "DiskColor",
              secondary="DiskWrite", autoscale=1, fill=False)

        # Bring the disk usage ring to within 41 px of the I/O graph.
        ring_x, ring_y, ring_size = 728, y + 6, 60
        ring = dict(X=px(ring_x), Y=px(ring_y), W=px(ring_size), H=px(ring_size),
                    StartAngle="(Rad(270))", RotationAngle="(Rad(360))",
                    LineStart=px(21), LineLength=px(29), Solid=1,
                    AntiAlias=1, UpdateDivider=interval, Group=group, Hidden=1)
        section(p + "DiskPieBackground", Meter="Roundline",
                MeasureName=p + "DiskTrack", LineColor="43,49,71", **ring)
        section(p + "DiskPie", Meter="Roundline", MeasureName=p + "Disk",
                LineColor="#PieColor#", DynamicVariables=1,
                ToolTipText=f"Used: [{p}DiskUsed] / [{p}DiskTotal] GB ([{p}Disk:0]%)",
                **ring)
        # CenterCenter anchors the percent at the geometric center of the ring.
        data(p, "DiskPercent", "%1%", ring_x, ring_y, ring_size,
             MeasureName=p + "Disk", NumOfDecimals=0,
             StringAlign="CenterCenter", FontSize=px(7),
             FontColor="#TextColor#", StringStyle="Bold", height=ring_size)
        data(p, "DiskDetail", "%1 / %2 ГБ", ring_x - 20, y + 75, 100,
             MeasureName=p + "DiskUsed", MeasureName2=p + "DiskTotal",
             NumOfDecimals=1, StringAlign="Center",
             FontSize=px(8), FontColor="#DiskColor#", height=16)

        for metric, meter, normal in (
            ("CPU", "CPUValue", "#CPUColor#"),
            ("RAM", "RAMValue", "#RAMColor#"),
            ("Disk", "DiskDetail", "#DiskColor#"),
        ):
            on = f'[!SetOption {p}{meter} FontColor "#WarningColor#"]'
            off = f'[!SetOption {p}{meter} FontColor "{normal}"]'
            if metric == "Disk":
                on += (f'[!SetOption {p}DiskPie LineColor "#WarningColor#"]'
                       f'[!SetOption {p}DiskPercent FontColor "#WarningColor#"]')
                off += (f'[!SetOption {p}DiskPie LineColor "#PieColor#"]'
                        f'[!SetOption {p}DiskPercent FontColor "#TextColor#"]')
            section(p + metric + "Warning", Measure="Calc", Formula=p + metric,
                    IfCondition=f"({p}{metric} >= 80)",
                    IfTrueAction=on, IfFalseAction=off)

    for i in range(configured + 1, row_count + 1):
        y = top(i)
        shape(f"VM{i}EmptyCard", 1, y + 1,
              f"Rectangle 0,0,{px(card_width - 2)},{px(card_height - 2)},12 | "
              "Fill Color #BackgroundColor# | Stroke Color #BorderColor# | StrokeWidth 1")
        shape(f"VM{i}EmptyDot", 14, y + 15,
              f"Ellipse {px(4)},{px(4)},{px(4)} | Fill Color 101,108,133 | StrokeWidth 0")
        text(f"VM{i}Empty", f"{i:02d} · не настроен", 28, y + 33, 300,
             FontSize=px(11), FontColor="#SubtleColor#", height=20)

    return ("; Generated by @Resources/Aggregate/generate.py. "
            "Edit servers.json, not this file.\n\n" + "\n".join(lines))


def save_config(config, path=CONFIG_PATH):
    validate(config)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def write_ini(output, content):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-16")
    temporary.replace(output)


def generate(config, output=SKIN_PATH):
    write_ini(output, render(config))
    return output


def render_shared_variables(config):
    validate(config)
    lines = ["; Generated from servers.json. Shared by all Aggregate variants.",
             "[Variables]", "HostTitle=" + config.get("host_title", "VIRTUAL MACHINES")]
    for i, server in enumerate((s for s in config["servers"] if s.get("enabled", True)), 1):
        address = server["address"]
        lines.extend([
            f"VM{i}Address={address}",
            f"VM{i}URLHost=" + (f"[{address}]" if ":" in address else address),
            f"VM{i}Port={int(server.get('port', 5000))}",
            f"VM{i}Name=" + (server.get("name") or server["id"]),
            f"VM{i}StatsPath={stats_path(server)}",
        ])
    return "\n".join(lines) + "\n"


def generate_all(config, output=SKIN_PATH):
    # Render everything before writing: invalid settings cannot leave a partial set.
    common = output.parent.parent / "@Resources" / "Aggregate" / "servers.inc"
    files = {common: render_shared_variables(config), output: render(config, shared=True)}
    for slots in range(1, 21):
        files[output.with_name(f"Aggregate-{slots:02d}.ini")] = render(config, slots=slots, shared=True)
    for path, content in files.items():
        write_ini(path, content)
    return output


def refresh():
    candidates = [shutil.which("Rainmeter.exe")]
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(env):
            candidates.append(str(Path(os.environ[env]) / "Rainmeter" / "Rainmeter.exe"))
    exe = next((p for p in candidates if p and Path(p).is_file()), None)
    config_name = SKIN_PATH.parent.parent.name + "\\Aggregate"
    if exe:
        subprocess.run([exe, "!Refresh", config_name], check=True)
    else:
        print(f"Rainmeter.exe not found. Refresh {config_name} manually.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Refresh installed Rainmeter skin after generation")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("generate")
    commands.add_parser("list")
    add = commands.add_parser("add")
    add.add_argument("address")
    add.add_argument("--id", required=True)
    add.add_argument("--name", default="")
    add.add_argument("--port", type=int, default=5000)
    add.add_argument("--demo-load", type=int, choices=(10, 50, 80, 100))
    remove = commands.add_parser("remove")
    remove.add_argument("id")
    args = parser.parse_args(argv)
    try:
        config = validate(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
        if args.command == "list":
            for s in config["servers"]:
                print(f"{s['id']}: {s['address']}:{s.get('port', 5000)} ({'on' if s.get('enabled', True) else 'off'})")
            return 0
        if args.command == "add":
            config["servers"].append(dict(id=args.id, address=args.address, name=args.name, port=args.port, enabled=True, demo_load=args.demo_load))
            save_config(config)
        elif args.command == "remove":
            if not any(s["id"] == args.id for s in config["servers"]):
                raise ValueError(f"Unknown id: {args.id}")
            config["servers"] = [s for s in config["servers"] if s["id"] != args.id]
            save_config(config)
        print(f"Generated: {generate_all(config)} + Aggregate-01.ini ... Aggregate-20.ini (shared servers.inc)")
        if args.refresh:
            refresh()
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
