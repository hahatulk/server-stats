"""Generate a compact Rainmeter skin from servers.json (Python 3.9+, no dependencies)."""
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
    row_height = 88
    panel_width = 828
    columns = 2 if row_count > 10 else 1
    column_offset = panel_width + 16
    width = panel_width + (columns-1)*column_offset
    rows_high = max(10, row_count-10) if columns == 2 else row_count

    def row_y(index):
        return 66 + ((index-1) if index <= 10 else (index-11))*row_height

    def px(n):
        return str(max(1, round(n * scale))) if n else "0"
    lines = []
    def section(name, **options):
        # Row coordinates stay local to one panel. Move every VM meter,
        # including Shape geometry and graphs, together into the second panel.
        match = re.match(r"VM(\d+)", name)
        if "Meter" in options and match and int(match.group(1)) > 10:
            options["X"] = str(int(options.get("X", 0)) + int(px(column_offset)))
        lines.append(f"[{name}]")
        lines.extend(f"{key}={value}" for key, value in options.items())
        lines.append("")
    height = 72 + rows_high * row_height if row_count else 120
    section("Rainmeter", Update=1000, AccurateText=1, DynamicWindowSize=0,
            ContextTitle="Открыть список виртуалок", ContextAction='["notepad.exe" "#@#Aggregate\\servers.json"]',
            ContextTitle2="Пересобрать и обновить", ContextAction2='["py.exe" "#@#Aggregate\\generate.py" "--refresh"]')
    section("Metadata", Name="ServerStats Aggregate" + (f" {slots:02d} VM" if slots else ""), Information="Compact VM overview. Configure @Resources/Aggregate/servers.json", Version="1.0")
    section("Variables", BackgroundColor="12,12,12,250", BorderColor="100,100,100,150",
            CPUColor="17,125,187", RAMColor="139,18,174", NetColor="237,165,130", DiskColor="77,166,12",
            WarningColor="240,85,85", DownloadColor="#NetColor#", UploadColor="100,200,255",
            **({"@Include": "#@#Aggregate\\servers.inc"} if shared else {}),
            **{f"VM{i}Online": -1 for i in range(1, len(servers)+1)},
            **{f"VM{i}NetUnit": "Кбит/с" for i in range(1, len(servers)+1)})
    section("TextStyle", FontFace="Segoe UI", FontSize=px(9), FontColor="255,255,255", AntiAlias=1,
            ClipString=1, H=px(19), DynamicVariables=0, UpdateDivider=-1)
    section("Background", Meter="Shape", UpdateDivider=-1, Shape=f"Rectangle 1,1,{px(width-2)},{px(height-2)},8 | Fill Color #BackgroundColor# | Stroke Color #BorderColor# | StrokeWidth 1")
    def text(name, value, x, y, w, **opts):
        if opts.get("StringAlign") == "Center":
            x += w / 2  # Rainmeter X is the anchor, not the left edge.
        section(name, Meter="String", MeterStyle="TextStyle", X=px(x), Y=px(y), W=px(w), Text=value, **opts)
    title = "#HostTitle#" if shared else config.get("host_title", "VIRTUAL MACHINES")
    text("Title", title, 14, 10, width-280, FontSize=px(13), StringStyle="Bold", H=px(25))
    text("Count", f"{configured}/{slots} VM" if slots is not None else f"{configured} VM", width-250, 14, 74, FontColor="178,178,178")
    text("Edit", "список", width-164, 14, 67, FontColor="178,178,178", SolidColor="255,255,255,1",
         LeftMouseUpAction='["notepad.exe" "#@#Aggregate\\servers.json"]', ToolTipText="Добавьте / удалите машины в JSON, затем нажмите обновить")
    text("Rebuild", "обновить", width-88, 14, 78, FontColor="178,178,178", SolidColor="255,255,255,1",
         LeftMouseUpAction='["py.exe" "#@#Aggregate\\generate.py" "--refresh"]', ToolTipText="Перечитать список и изменить размер (нужен Python Launcher py.exe)")
    for column in range(columns):
        for name, label, x, w, color in [("Host", "HOSTNAME / IP", 24, 141, "178,178,178"), ("CPU", "ЦП", 176, 48, "#CPUColor#"),
                ("RAM", "ОЗУ", 236, 148, "#RAMColor#"), ("Net", "СЕТЬ", 398, 146, "#NetColor#"),
                ("DiskIO", "I/O", 552, 136, "#DiskColor#"), ("Disk", "ДИСК", 696, 118, "#DiskColor#")]:
            text("Column"+("2" if column else "")+name, label, x+column*column_offset, 44, w,
                 FontColor=color, FontSize=px(8), StringAlign="Left" if name == "Host" else "Center")
    if columns == 2:
        section("PanelSeparator", Meter="Shape", UpdateDivider=-1,
                Shape=f"Line {px(panel_width+8)},{px(44)},{px(panel_width+8)},{px(height-14)} | Stroke Color 255,255,255,35 | StrokeWidth 1")
    if not row_count:
        text("Empty", "Список пуст. Нажмите «список», добавьте машины и нажмите «обновить».", 24, 82, 710)
    number = r"([0-9]+(?:\.[0-9]+)?)"
    regexp = "(?s)^CPU:" + number + ";RAM:" + number + ";RAM_USED:" + number + ";RAM_TOTAL:" + number + ";NET_RECV:" + number + ";NET_SENT:" + number + ";HOSTNAME:([^;\\r\\n]+);DISK_PERCENT:" + number + ";DISK_USED:" + number + ";DISK_TOTAL:" + number + ";DISK_READ:" + number + ";DISK_WRITE:" + number + "(?:;|$)"
    for i, server in enumerate(servers, 1):
        p = f"VM{i}"
        y = row_y(i)
        group = p + "Data"
        # Async callbacks only publish a scalar state. Never rebuild geometry or
        # force a whole-skin update for each VM response (including repeated errors).
        fail = f'[!SetVariable {p}Online 0]'
        ok = f'[!SetVariable {p}Online 1]'
        address = server["address"]
        urlhost = f"[{address}]" if ":" in address else address
        section(p+"Source", Measure="WebParser", URL=(f"http://#{p}URLHost#:#{p}Port#/#{p}StatsPath#" if shared else f"http://{urlhost}:{int(server.get('port',5000))}/{stats_path(server)}"),
                RegExp=regexp, UpdateRate=int(config.get("update_seconds", 2)),
                Flags="ForceReload | NoCacheWrite | NoCookies", ProxyServer="/none",
                FinishAction=ok, OnConnectErrorAction=fail, OnRegExpErrorAction=fail, OnDownloadErrorAction=fail)
        # Only state transitions change visibility / retry rate. A failed VM is
        # retried at most once per 30s, not at the normal high-frequency rate.
        online = (f'[!ShowMeterGroup {group}][!HideMeter {p}Offline]'
                  f'[!HideMeter {p}DotWaiting][!HideMeter {p}DotOffline][!ShowMeter {p}DotOnline]'
                  f'[!SetOption {p}Source UpdateRate {int(config.get("update_seconds", 2))}]')
        offline = (f'[!HideMeterGroup {group}][!ShowMeter {p}Offline]'
                   f'[!HideMeter {p}DotWaiting][!HideMeter {p}DotOnline][!ShowMeter {p}DotOffline]'
                   f'[!SetOption {p}Source UpdateRate {max(30, int(config.get("update_seconds", 2)))}]')
        section(p+"Connection", Measure="Calc", Formula=f"#{p}Online#", DynamicVariables=1,
                IfCondition=f"({p}Connection = 1)", IfTrueAction=online,
                IfCondition2=f"({p}Connection = 0)", IfTrueAction2=offline)
        for index, field in enumerate(["CPU", "RAM", "RAMUsed", "RAMTotal", "Recv", "Sent", "Hostname", "Disk", "DiskUsed", "DiskTotal", "DiskRead", "DiskWrite"], 1):
            options = dict(Measure="WebParser", URL=f"[{p}Source]", StringIndex=index)
            if field in ("CPU", "RAM", "Disk"):
                options.update(MinValue=0, MaxValue=100)
            if field == "Hostname":
                options["Substitute"] = '\"\":\"' + (f"#{p}Name#" if shared else (server.get("name") or server["id"])) + '\"'
            section(p+field, **options)
        # Input is decimal Mbit/s. Choose one unit for both directions from
        # their maximum, but never rescale stored graph samples when units change.
        section(p+"NetPeak", Measure="Calc", Formula=f"Max({p}Recv, {p}Sent)", MinValue=0)
        section(p+"NetScale", Measure="Calc", Formula=f"({p}NetPeak >= 1000 ? 1000 : ({p}NetPeak >= 1 ? 1 : 0.001))",
                IfCondition=f"({p}NetScale = 0.001)", IfTrueAction=f'[!SetVariable {p}NetUnit "Кбит/с"]',
                IfCondition2=f"({p}NetScale = 1)", IfTrueAction2=f'[!SetVariable {p}NetUnit "Мбит/с"]',
                IfCondition3=f"({p}NetScale = 1000)", IfTrueAction3=f'[!SetVariable {p}NetUnit "Гбит/с"]')
        for direction, source in (("Recv", "Recv"), ("Sent", "Sent")):
            section(p+"Net"+direction+"Display", Measure="Calc", Formula=f"Round({p}{source} / {p}NetScale, 1)", MinValue=0, NumOfDecimals=1)
        section(p+"DiskTotalIO", Measure="Calc", Formula=f"{p}DiskRead + {p}DiskWrite", MinValue=0)
        # Separate Calc measures track both edges of the threshold; WebParser's
        # child measures retain their numeric values even when percentages are hidden.
        for metric, targets in [
            ("CPU", [("CPUValue", "178,178,178")]),
            ("RAM", [("RAMValue", "178,178,178")]),
            ("Disk", [("DiskDetail", "178,178,178"), ("DiskIO", "#DiskColor#")]),
        ]:
            hot = "".join(f'[!SetOption {p}{name} FontColor "#WarningColor#"]' for name, _ in targets)
            normal = "".join(f'[!SetOption {p}{name} FontColor "{color}"]' for name, color in targets)
            if metric == "Disk":
                # Inline colors otherwise override FontColor, including alarms.
                hot += (f'[!SetOption {p}DiskPie LineColor "#WarningColor#"]'
                        f'[!SetOption {p}DiskIO InlineSetting "Color | #WarningColor#"]'
                        f'[!SetOption {p}DiskIO InlineSetting2 "Color | #WarningColor#"]')
                normal += (f'[!SetOption {p}DiskPie LineColor "#DiskColor#"]'
                           f'[!SetOption {p}DiskIO InlineSetting "Color | #DownloadColor#"]'
                           f'[!SetOption {p}DiskIO InlineSetting2 "Color | #UploadColor#"]')
            section(p+metric+"Warning", Measure="Calc", Formula=p+metric,
                    IfCondition=f"({p}{metric} >= 80)",
                    IfTrueAction=hot, IfFalseAction=normal)
        section(p+"Separator", Meter="Shape", UpdateDivider=-1, Shape=f"Line {px(14)},{px(y-2)},{px(panel_width-14)},{px(y-2)} | Stroke Color 255,255,255,22 | StrokeWidth 1")
        for state, color in [("Waiting", "130,130,130"), ("Online", "100,200,125"), ("Offline", "220,90,80")]:
            section(p+"Dot"+state, Meter="Shape", UpdateDivider=-1,
                    Hidden=0 if state == "Waiting" else 1,
                    Shape=f"Ellipse {px(15)},{px(y+13)},{px(3)} | Fill Color {color} | StrokeWidth 0")
        text(p+"Name", "%1", 24, y+2, 140, MeasureName=p+"Hostname", UpdateDivider=1, DynamicVariables=1,
             ToolTipText=f"{('#'+p+'Name#') if shared else (server.get('name') or server['id'])} · [{p}Hostname]", StringStyle="Bold")
        text(p+"Address", f"#{p}Address#" if shared else address, 24, y+24, 140, FontColor="178,178,178", FontSize=px(8))
        text(p+"Offline", "Ожидание / недоступен · нужен новый агент", 176, y+15, 610, FontColor="200,125,105")
        def data(name, value, x, yy, w, **opts):
            text(p+name, value, x, yy, w, Group=group, Hidden=1, UpdateDivider=1, StringAlign="Center", **opts)
        data("CPUValue", "%1%", 176, y+3, 48, MeasureName=p+"CPU", NumOfDecimals=0, FontColor="178,178,178")
        data("RAMValue", f"%1 / %2 GB ([{p}RAM:0]%)", 236, y+3, 148,
             MeasureName=p+"RAMUsed", MeasureName2=p+"RAMTotal", NumOfDecimals=1, FontSize=px(9), FontColor="178,178,178", DynamicVariables=1,
             ToolTipText=f"ОЗУ: [{p}RAMUsed] / [{p}RAMTotal] GB ([{p}RAM:0]%)")
        data("NetValue", f"↓%1 ↑%2 #{p}NetUnit#", 398, y+3, 146, MeasureName=p+"NetRecvDisplay", MeasureName2=p+"NetSentDisplay",
             NumOfDecimals=1, FontSize=px(9), FontColor="178,178,178", DynamicVariables=1,
             InlineSetting="Color | #DownloadColor#", InlinePattern=r"↓[0-9.]+",
             InlineSetting2="Color | #UploadColor#", InlinePattern2=r"↑[0-9.]+",
             ToolTipText=f"Приём: [{p}NetRecvDisplay:1] #{p}NetUnit# · Отправка: [{p}NetSentDisplay:1] #{p}NetUnit#")
        section(p+"NetGraph", Meter="Line", MeasureName=p+"Recv", MeasureName2=p+"Sent", LineCount=2,
                X=px(399), Y=px(y+24), W=px(144), H=px(36), LineWidth=1,
                LineColor="#DownloadColor#", LineColor2="#UploadColor#", AutoScale=1, AntiAlias=1,
                UpdateDivider=1, Group=group, Hidden=1, DynamicVariables=1,
                ToolTipText=f"Приём: [{p}NetRecvDisplay:1] #{p}NetUnit# · Отправка: [{p}NetSentDisplay:1] #{p}NetUnit# (автомасштаб)")
        section(p+"NetGraphFrame", Meter="Shape", UpdateDivider=-1, Group=group, Hidden=1,
                Shape=f"Rectangle {px(398)},{px(y+23)},{px(146)},{px(38)} | Fill Color 0,0,0,0 | Stroke Color #NetColor# | StrokeWidth 1")
        data("DiskDetail", "%1 / %2 GB", 690, y+46, 130, MeasureName=p+"DiskUsed", MeasureName2=p+"DiskTotal",
             NumOfDecimals=1, FontSize=px(9), FontColor="178,178,178", DynamicVariables=1,
             ToolTipText=f"Занято: [{p}DiskUsed] / [{p}DiskTotal] GB")
        data("DiskIO", "R %1 W %2 MB/s", 552, y+3, 136, MeasureName=p+"DiskRead", MeasureName2=p+"DiskWrite",
             NumOfDecimals=1, FontSize=px(9), H=px(19), FontColor="#DiskColor#", DynamicVariables=1,
             InlineSetting="Color | #DownloadColor#", InlinePattern=r"R [0-9.]+",
             InlineSetting2="Color | #UploadColor#", InlinePattern2=r"W [0-9.]+",
             ToolTipText=f"Чтение: [{p}DiskRead] MB/s · Запись: [{p}DiskWrite] MB/s (все диски ВМ)")
        # Native Rainmeter graphs retain only a fixed-width window of samples.
        # No Python/Lua history, growing paths or per-response geometry rebuilding.
        for metric, x, w, color in [("CPU",176,48,"CPUColor"), ("RAM",236,148,"RAMColor")]:
            common = dict(MeasureName=p+metric, X=px(x+1), Y=px(y+24),
                          W=px(w-2), H=px(36), UpdateDivider=1, AntiAlias=1,
                          AutoScale=0, Group=group, Hidden=1)
            section(p+metric+"GraphFill", Meter="Histogram", PrimaryColor=f"#{color}#,30", **common)
            section(p+metric+"Graph", Meter="Line", LineCount=1,
                    LineColor=f"#{color}#", LineWidth=1, **common)
            section(p+metric+"GraphFrame", Meter="Shape", UpdateDivider=-1, Group=group, Hidden=1,
                    Shape=f"Rectangle {px(x)},{px(y+23)},{px(w)},{px(38)} | Fill Color 0,0,0,0 | Stroke Color #{color}# | StrokeWidth 1")
        section(p+"DiskPieBackground", Meter="Shape", UpdateDivider=-1, Group=group, Hidden=1,
                Shape=f"Ellipse {px(755)},{px(y+22)},{px(15)} | Fill Color 255,255,255,28 | StrokeWidth 0")
        section(p+"DiskPie", Meter="Roundline", MeasureName=p+"Disk", X=px(739), Y=px(y+6), W=px(32), H=px(32),
                StartAngle="(Rad(270))", RotationAngle="(Rad(360))", LineStart=0, LineLength=px(15),
                Solid=1, LineColor="#DiskColor#", AntiAlias=1, UpdateDivider=1, Group=group, Hidden=1,
                DynamicVariables=1, ToolTipText=f"Занято: [{p}DiskUsed] / [{p}DiskTotal] GB ([{p}Disk:0]%)")
        # I/O is throughput, not disk-space percentage: use an autoscaled sum.
        disk_graph = dict(MeasureName=p+"DiskTotalIO", X=px(553), Y=px(y+24), W=px(134), H=px(36),
                          AutoScale=1, AntiAlias=1, UpdateDivider=1, Group=group, Hidden=1)
        section(p+"DiskIOGraphFill", Meter="Histogram", PrimaryColor="#DiskColor#,30", **disk_graph)
        section(p+"DiskIOGraph", Meter="Line", LineCount=1, LineColor="#DiskColor#", LineWidth=1,
                DynamicVariables=1,
                ToolTipText=f"Чтение + запись: [{p}DiskTotalIO:1] MB/s (автомасштаб)", **disk_graph)
        section(p+"DiskIOGraphFrame", Meter="Shape", UpdateDivider=-1, Group=group, Hidden=1,
                Shape=f"Rectangle {px(552)},{px(y+23)},{px(136)},{px(38)} | Fill Color 0,0,0,0 | Stroke Color #DiskColor# | StrokeWidth 1")
    for i in range(configured+1, row_count+1):
        y = row_y(i)
        section(f"VM{i}EmptySeparator", Meter="Shape", UpdateDivider=-1,
                Shape=f"Line {px(14)},{px(y-2)},{px(panel_width-14)},{px(y-2)} | Stroke Color 255,255,255,22 | StrokeWidth 1")
        text(f"VM{i}Empty", f"{i:02d} · не настроено", 24, y+12, 710, FontColor="130,130,130")
    return "; Generated by @Resources/Aggregate/generate.py. Edit servers.json, not this file.\n\n" + "\n".join(lines)


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
