import configparser
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "ServerStats/@Resources/Aggregate/generate.py"
spec = importlib.util.spec_from_file_location("aggregate_generate", SCRIPT)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def configuration(count=1):
    return {"host_title": "HOST-01", "servers": [
        {"id": f"vm{i}", "address": f"192.168.1.{i+1}"} for i in range(count)
    ]}


def parse(config):
    parser = configparser.RawConfigParser(strict=True)
    parser.read_string(generator.render(config))
    return parser


class AggregateTests(unittest.TestCase):
    def test_exact_number_of_rows_and_height(self):
        for count in (0, 1, 10, 20, 30):
            with self.subTest(count=count):
                skin = parse(configuration(count))
                sources = [s for s in skin.sections() if re.fullmatch(r"VM\d+Source", s)]
                self.assertEqual(len(sources), count)
                rows = max(10, count-10) if count > 10 else count
                height = 72 + rows*88 if count else 120
                self.assertIn(f",{height-2},8", skin["Background"]["Shape"])

    def test_disabled_rows_are_not_polled_or_counted(self):
        config = configuration(3)
        config["servers"][1]["enabled"] = False
        skin = parse(config)
        self.assertEqual(skin["Count"]["Text"], "2 VM")
        self.assertEqual(skin["VM2Source"]["URL"], "http://192.168.1.3:5000/stats")
        self.assertNotIn("VM3Source", skin)

    def test_wire_format_capture_order(self):
        skin = parse(configuration())
        response = "CPU:12.5;RAM:60.0;RAM_USED:3.0;RAM_TOTAL:5.0;NET_RECV:1.2;NET_SENT:0.3;HOSTNAME:vm-linux;DISK_PERCENT:40.0;DISK_USED:20.0;DISK_TOTAL:50.0;DISK_READ:12.5;DISK_WRITE:3.2"
        match = re.search(skin["VM1Source"]["RegExp"], response)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("12.5", "60.0", "3.0", "5.0", "1.2", "0.3", "vm-linux", "40.0", "20.0", "50.0", "12.5", "3.2"))
        self.assertEqual(skin["VM1DiskRead"]["StringIndex"], "11")
        self.assertEqual(skin["VM1DiskWrite"]["StringIndex"], "12")
        self.assertEqual(skin["VM1DiskIO"]["MeasureName"], "VM1DiskRead")
        self.assertEqual(skin["VM1DiskIO"]["MeasureName2"], "VM1DiskWrite")
        self.assertEqual(skin["VM1DiskIO"]["Group"], "VM1Data")
        self.assertIsNone(re.search(skin["VM1Source"]["RegExp"], response.split(";DISK_READ")[0]))
        self.assertIsNone(re.search(skin["VM1Source"]["RegExp"], response.split(";HOSTNAME")[0]))

    def test_offline_hides_stale_metrics(self):
        skin = parse(configuration())
        self.assertEqual(skin["VM1Source"]["OnConnectErrorAction"], "[!SetVariable VM1Online 0]")
        self.assertEqual(skin["VM1Source"]["OnRegExpErrorAction"], "[!SetVariable VM1Online 0]")
        self.assertEqual(skin["VM1Source"]["FinishAction"], "[!SetVariable VM1Online 1]")
        self.assertIn("!HideMeterGroup VM1Data", skin["VM1Connection"]["IfTrueAction2"])
        self.assertIn("!ShowMeterGroup VM1Data", skin["VM1Connection"]["IfTrueAction"])
        self.assertEqual(skin["VM1CPUValue"]["Hidden"], "1")

    def test_poll_callbacks_do_not_recreate_render_resources(self):
        skin = parse(configuration(20))
        rendered = generator.render(configuration(20))
        self.assertNotIn("!UpdateMeter *", rendered)
        self.assertNotIn("!Redraw", rendered)
        self.assertNotRegex(rendered, r"!SetOption [^ ]+ Shape ")
        self.assertEqual(skin["Rainmeter"]["DynamicWindowSize"], "0")
        for i in range(1, 21):
            source = skin[f"VM{i}Source"]
            self.assertNotIn("ForceReload", source)
            self.assertEqual(source["Flags"], "ForceReload | NoCacheWrite | NoCookies")
            self.assertEqual(source["ProxyServer"], "/none")
            connection = skin[f"VM{i}Connection"]
            self.assertEqual(connection["Formula"], f"#VM{i}Online#")
            self.assertEqual(connection["DynamicVariables"], "1")
            self.assertNotIn("IfConditionMode", connection)  # default = edge-triggered
            self.assertIn(f"!SetOption VM{i}Source UpdateRate 30", connection["IfTrueAction2"])
            self.assertIn(f"!SetOption VM{i}Source UpdateRate 2", connection["IfTrueAction"])
            for state in ("Waiting", "Online", "Offline"):
                self.assertEqual(skin[f"VM{i}Dot{state}"]["UpdateDivider"], "-1")
        self.assertEqual(skin["Background"]["UpdateDivider"], "-1")
        self.assertEqual(skin["TextStyle"]["DynamicVariables"], "0")
        self.assertEqual(skin["TextStyle"]["UpdateDivider"], "-1")
        self.assertEqual(skin["VM1CPUValue"]["UpdateDivider"], "1")
        self.assertEqual(skin["VM1CPUGraph"]["UpdateDivider"], "2")

    def test_cpu_and_ram_graphs_are_fixed_size_native_meters(self):
        skin = parse(configuration(2))
        for i in (1, 2):
            for metric, width, color in (("CPU", 46, "CPUColor"), ("RAM", 146, "RAMColor")):
                prefix = f"VM{i}{metric}"
                self.assertNotIn(prefix+"Bar", skin)
                line, fill, frame = (skin[prefix+suffix] for suffix in ("Graph", "GraphFill", "GraphFrame"))
                self.assertEqual(line["Meter"], "Line")
                self.assertEqual(fill["Meter"], "Histogram")
                self.assertEqual(line["LineColor"], f"#{color}#")
                self.assertEqual(fill["PrimaryColor"], f"#{color}#,30")
                for graph in (line, fill):
                    self.assertEqual(graph["MeasureName"], prefix)
                    self.assertEqual(graph["W"], str(width))
                    self.assertEqual(graph["H"], "36")
                    self.assertEqual(graph["AutoScale"], "0")
                    self.assertEqual(graph["Group"], f"VM{i}Data")
                    self.assertEqual(graph["UpdateDivider"], "2")
                self.assertEqual(frame["UpdateDivider"], "-1")
                self.assertEqual(skin[prefix]["MaxValue"], "100")
        self.assertNotIn("VM1DiskBar", skin)
        self.assertEqual(skin["VM1DiskPie"]["Meter"], "Roundline")

    def test_two_columns_start_at_vm_eleven_and_move_all_row_meters(self):
        for count in (10, 11, 20, 30):
            skin = parse(configuration(count))
            two_columns = count > 10
            self.assertEqual("Column2Host" in skin, two_columns)
            self.assertEqual("PanelSeparator" in skin, two_columns)
            expected_width = 1670 if two_columns else 826
            self.assertTrue(skin["Background"]["Shape"].startswith(f"Rectangle 1,1,{expected_width},"))
            if two_columns:
                self.assertEqual(int(skin["Column2CPU"]["X"])-int(skin["ColumnCPU"]["X"]), 844)
                for suffix in ("Name", "Address", "Offline", "CPUValue", "RAMValue", "NetValue", "NetGraph",
                               "DiskDetail", "DiskIO", "CPUGraph", "CPUGraphFill", "RAMGraph", "RAMGraphFill",
                               "DiskPie", "DiskIOGraph", "DiskIOGraphFill"):
                    with self.subTest(count=count, suffix=suffix):
                        first, second = skin["VM1"+suffix], skin["VM11"+suffix]
                        self.assertEqual(int(second["X"])-int(first["X"]), 844)
                        self.assertEqual(second["Y"], first["Y"])
                for suffix in ("Separator", "DotWaiting", "DotOnline", "DotOffline", "CPUGraphFrame",
                               "RAMGraphFrame", "NetGraphFrame", "DiskPieBackground", "DiskIOGraphFrame"):
                    self.assertEqual(skin["VM11"+suffix]["X"], "844")
                self.assertEqual(skin["VM1CPUGraph"]["H"], "36")
                self.assertEqual(skin["VM11DiskIOGraph"]["H"], "36")
            if count >= 20:
                self.assertEqual(skin["VM20Name"]["Y"], skin["VM10Name"]["Y"])
            if count == 30:
                self.assertEqual(skin["VM30Name"]["X"], skin["VM11Name"]["X"])
                self.assertGreater(int(skin["VM30Name"]["Y"]), int(skin["VM20Name"]["Y"]))
        empty = configparser.RawConfigParser()
        empty.read_string(generator.render(configuration(0), slots=20))
        self.assertEqual(empty["VM11Empty"]["X"], "868")
        self.assertEqual(empty["VM11Empty"]["Y"], empty["VM1Empty"]["Y"])
        self.assertEqual(empty["VM11EmptySeparator"]["X"], "844")

    def test_compact_network_dark_background_and_disk_visualizations(self):
        skin = parse(configuration())
        self.assertEqual(skin["Variables"]["BackgroundColor"], "12,12,12,250")
        self.assertEqual(skin["ColumnNet"]["Text"], "NETWORK")
        self.assertEqual(skin["VM1NetValue"]["Text"], "↓%1 ↑%2 #VM1NetUnit#")
        self.assertEqual(skin["VM1NetValue"]["W"], "146")
        self.assertNotIn("VM1NetDetail", skin)
        pie = skin["VM1DiskPie"]
        self.assertEqual(pie["MeasureName"], "VM1Disk")
        self.assertEqual(pie["Solid"], "1")
        self.assertEqual(pie["RotationAngle"], "(Rad(360))")
        self.assertEqual(pie["Group"], "VM1Data")
        self.assertEqual(skin["VM1DiskPieBackground"]["UpdateDivider"], "-1")
        self.assertEqual(skin["VM1DiskTotalIO"]["Formula"], "VM1DiskRead + VM1DiskWrite")
        for suffix in ("Graph", "GraphFill"):
            graph = skin["VM1DiskIO"+suffix]
            self.assertEqual(graph["MeasureName"], "VM1DiskTotalIO")
            self.assertEqual(graph["AutoScale"], "1")
            self.assertEqual(graph["UpdateDivider"], "2")
            self.assertEqual(graph["Group"], "VM1Data")
        self.assertEqual(skin["VM1DiskIOGraph"]["LineColor"], "#DiskColor#")
        self.assertEqual(skin["VM1DiskIOGraphFill"]["PrimaryColor"], "#DiskColor#,30")
        self.assertIn('VM1DiskPie LineColor "#WarningColor#"', skin["VM1DiskWarning"]["IfTrueAction"])
        self.assertIn('VM1DiskPie LineColor "#DiskColor#"', skin["VM1DiskWarning"]["IfFalseAction"])

    def test_disk_io_colors_match_network_and_alarm_overrides_both(self):
        skin = parse(configuration())
        disk = skin["VM1DiskIO"]
        self.assertEqual(skin["VM1NetValue"]["InlineSetting"], "Color | #DownloadColor#")
        self.assertEqual(skin["VM1NetValue"]["InlineSetting2"], "Color | #UploadColor#")
        self.assertEqual(disk["InlineSetting"], "Color | #DownloadColor#")
        self.assertEqual(disk["InlineSetting2"], "Color | #UploadColor#")
        self.assertEqual(re.findall(disk["InlinePattern"], "R 12.5 W 3.2 MB/s"), ["R 12.5"])
        self.assertEqual(re.findall(disk["InlinePattern2"], "R 12.5 W 3.2 MB/s"), ["W 3.2"])
        warning = skin["VM1DiskWarning"]
        for suffix, color in (("", "DownloadColor"), ("2", "UploadColor")):
            self.assertIn(f'InlineSetting{suffix} "Color | #WarningColor#"', warning["IfTrueAction"])
            self.assertIn(f'InlineSetting{suffix} "Color | #{color}#"', warning["IfFalseAction"])

    def test_network_dual_line_graph_and_gray_cpu_ram(self):
        skin = parse(configuration(20))
        for i in (1, 11, 20):
            prefix = f"VM{i}"
            value = skin[prefix+"NetValue"]
            self.assertEqual(value["FontSize"], skin["TextStyle"]["FontSize"])
            self.assertEqual(value["MeasureName"], prefix+"NetRecvDisplay")
            self.assertEqual(value["MeasureName2"], prefix+"NetSentDisplay")
            self.assertEqual(re.findall(value["InlinePattern"], "↓12.3 ↑1.2 Mbit/s"), ["↓12.3"])
            self.assertEqual(re.findall(value["InlinePattern2"], "↓12.3 ↑1.2 Mbit/s"), ["↑1.2"])
            graph = skin[prefix+"NetGraph"]
            self.assertEqual(graph["Meter"], "Line")
            self.assertEqual(graph["MeasureName"], prefix+"Recv")
            self.assertEqual(graph["MeasureName2"], prefix+"Sent")
            self.assertEqual(graph["LineCount"], "2")
            self.assertEqual(graph["LineColor"], "#DownloadColor#")
            self.assertEqual(graph["LineColor2"], "#UploadColor#")
            self.assertEqual(graph["H"], "36")
            self.assertEqual(graph["W"], "144")
            self.assertEqual(graph["AutoScale"], "1")
            self.assertEqual(graph["Group"], prefix+"Data")
            self.assertEqual(graph["UpdateDivider"], "2")
            self.assertEqual(skin[prefix+"NetGraphFrame"]["UpdateDivider"], "-1")
            for metric in ("CPU", "RAM"):
                self.assertEqual(skin[prefix+metric+"Value"]["FontColor"], skin[prefix+"DiskDetail"]["FontColor"])
                self.assertIn('FontColor "178,178,178"', skin[prefix+metric+"Warning"]["IfFalseAction"])

    def test_generated_interface_uses_english_text(self):
        for count in (0, 1, 20):
            content = generator.render(configuration(count), slots=20)
            self.assertIsNone(re.search(r"[\u0400-\u04ff]", content))
            skin = configparser.RawConfigParser()
            skin.read_string(content)
            self.assertEqual(skin["Edit"]["Text"], "list")
            self.assertEqual(skin["Rebuild"]["Text"], "refresh")
            self.assertEqual(skin["ColumnCPU"]["Text"], "CPU")
            self.assertEqual(skin["ColumnRAM"]["Text"], "RAM")

    def test_graph_sampling_matches_configured_poll_interval(self):
        for interval in (1, 2, 5, 60):
            config = configuration(20)
            config["update_seconds"] = interval
            skin = parse(config)
            self.assertEqual(skin["Rainmeter"]["Update"], "1000")
            for i in (1, 10, 11, 20):
                prefix = f"VM{i}"
                self.assertEqual(skin[prefix+"Source"]["UpdateRate"], str(interval))
                for suffix in ("CPUGraph", "CPUGraphFill", "RAMGraph", "RAMGraphFill",
                               "NetGraph", "DiskIOGraph", "DiskIOGraphFill"):
                    self.assertEqual(skin[prefix+suffix]["UpdateDivider"], str(interval))

    def test_network_adaptive_unit_thresholds_and_round_trip(self):
        skin = parse(configuration())
        self.assertEqual(skin["Variables"]["VM1NetUnit"], "Kbit/s")
        self.assertEqual(skin["VM1NetPeak"]["Formula"], "Max(VM1Recv, VM1Sent)")
        self.assertEqual(skin["VM1NetScale"]["Formula"], "(VM1NetPeak >= 1000 ? 1000 : (VM1NetPeak >= 1 ? 1 : 0.001))")
        scale = skin["VM1NetScale"]
        cases = [(0, 0, 0.001, "Kbit/s"), (0.000008, 0.125, 0.001, "Kbit/s"),
                 (0.999, 0, 0.001, "Kbit/s"), (0, 1, 1, "Mbit/s"),
                 (999.999, 2, 1, "Mbit/s"), (1, 1000, 1000, "Gbit/s"),
                 (2500, 500, 1000, "Gbit/s"), (0.05, 0.025, 0.001, "Kbit/s")]
        for recv, sent, divisor, unit in cases:
            values = {"VM1NetScale": divisor}
            matched = []
            for suffix in ("", "2", "3"):
                expression = scale["IfCondition"+suffix].replace(" = ", " == ")
                if eval(expression, {}, values):
                    matched.append(scale["IfTrueAction"+suffix])
            self.assertEqual(matched, [f'[!SetVariable VM1NetUnit "{unit}"]'])
            for direction, value in (("Recv", recv), ("Sent", sent)):
                measure = skin[f"VM1Net{direction}Display"]
                formula = measure["Formula"]
                self.assertEqual(formula, f"Round(VM1{direction} / VM1NetScale, 1)")
                converted = eval(formula, {}, {"Round": round, "VM1NetScale": divisor, f"VM1{direction}": value})
                self.assertEqual(converted, round(value/divisor, 1))
                self.assertEqual(measure["NumOfDecimals"], "1")
                self.assertEqual(skin["VM1NetValue"]["NumOfDecimals"], "1")
        self.assertEqual(skin["VM1NetGraph"]["MeasureName"], "VM1Recv")
        self.assertEqual(skin["VM1NetGraph"]["MeasureName2"], "VM1Sent")

    def test_uniform_value_fonts_and_disk_spacing(self):
        skin = parse(configuration(20))
        for i in (1, 10, 11, 20):
            prefix = f"VM{i}"
            for suffix in ("CPUValue", "RAMValue", "NetValue", "DiskDetail", "DiskIO"):
                meter = skin[prefix+suffix]
                self.assertEqual(meter.get("FontSize", skin["TextStyle"]["FontSize"]), "9")
            detail, io, graph = (skin[prefix+suffix] for suffix in ("DiskDetail", "DiskIO", "DiskIOGraph"))
            pie = skin[prefix+"DiskPie"]
            self.assertGreater(int(pie["X"]), int(graph["X"])+int(graph["W"]))
            self.assertGreater(int(detail["X"]), int(graph["X"])+int(graph["W"]))
            self.assertGreaterEqual(int(detail["Y"])-int(pie["Y"])-int(pie["H"]), 8)
            self.assertGreaterEqual(int(graph["Y"])-int(io["Y"])-int(io["H"]), 2)
            self.assertEqual(graph["Y"], skin[prefix+"RAMGraph"]["Y"])
            self.assertEqual(graph["H"], skin[prefix+"RAMGraph"]["H"])
            self.assertEqual(skin[prefix+"Name"]["W"], "140")
            self.assertEqual(skin[prefix+"Address"]["W"], "140")
            self.assertGreaterEqual(int(skin[prefix+"NetValue"]["W"]), 136)
            self.assertLessEqual(int(skin[prefix+"NetGraph"]["X"])+int(skin[prefix+"NetGraph"]["W"]), int(skin[prefix+"DiskPie"]["X"]))

    def test_values_and_headers_are_centered_on_their_graphs(self):
        skin = parse(configuration(20))
        for i in (1, 11, 20):
            prefix = f"VM{i}"
            for value, graph, header in (("CPUValue", "CPUGraph", "CPU"), ("RAMValue", "RAMGraph", "RAM"),
                                         ("NetValue", "NetGraph", "Net"), ("DiskIO", "DiskIOGraph", "DiskIO")):
                meter, plot = skin[prefix+value], skin[prefix+graph]
                self.assertEqual(meter["StringAlign"], "Center")
                center = int(plot["X"]) + int(plot["W"])/2
                self.assertEqual(int(meter["X"]), center)
                column = skin["Column"+("2" if i > 10 else "")+header]
                self.assertEqual(column["StringAlign"], "Center")
                self.assertEqual(int(column["X"]), center)
            detail, pie = skin[prefix+"DiskDetail"], skin[prefix+"DiskPie"]
            self.assertEqual(detail["StringAlign"], "Center")
            self.assertEqual(int(detail["X"]), int(pie["X"])+int(pie["W"])/2)
        self.assertEqual(skin["ColumnHost"]["StringAlign"], "Left")

    def test_backoff_never_increases_polling_frequency(self):
        config = configuration()
        config["update_seconds"] = 60
        skin = parse(config)
        self.assertIn("!SetOption VM1Source UpdateRate 60", skin["VM1Connection"]["IfTrueAction2"])

    def test_compact_ram_and_disk_values(self):
        skin = parse(configuration())
        self.assertNotIn("VM1RAMDetail", skin)
        self.assertEqual(skin["VM1RAMValue"]["Text"], "%1 / %2 GB ([VM1RAM:0]%)")
        self.assertEqual(skin["VM1RAMValue"]["MeasureName"], "VM1RAMUsed")
        self.assertEqual(skin["VM1RAMValue"]["MeasureName2"], "VM1RAMTotal")
        self.assertNotIn("VM1DiskValue", skin)
        self.assertEqual(skin["VM1DiskDetail"]["Text"], "%1 / %2 GB")
        self.assertEqual(skin["VM1DiskDetail"]["W"], "130")
        self.assertEqual(skin["VM1DiskIO"]["Text"], "R %1 W %2 MB/s")
        self.assertEqual(skin["VM1DiskIO"]["NumOfDecimals"], "1")
        self.assertEqual(skin["ColumnDisk"]["Text"], "DISK")
        self.assertEqual(skin["ColumnDiskIO"]["Text"], "I/O")
        self.assertIn("VM1DiskIO", skin)

    def test_warning_thresholds_and_color_recovery(self):
        skin = parse(configuration(2))
        for i in (1, 2):
            for metric, targets in (
                ("CPU", [("CPUValue", "178,178,178")]),
                ("RAM", [("RAMValue", "178,178,178")]),
                ("Disk", [("DiskDetail", "178,178,178"), ("DiskIO", "#DiskColor#")]),
            ):
                warning = skin[f"VM{i}{metric}Warning"]
                self.assertEqual(warning["Formula"], f"VM{i}{metric}")
                self.assertEqual(warning["IfCondition"], f"(VM{i}{metric} >= 80)")
                for value, expected in ((79.9, False), (80, True), (100, True)):
                    self.assertEqual(eval(warning["IfCondition"], {f"VM{i}{metric}": value}), expected)
                for meter, normal in targets:
                    self.assertIn(f'VM{i}{meter} FontColor "#WarningColor#"', warning["IfTrueAction"])
                    self.assertIn(f'VM{i}{meter} FontColor "{normal}"', warning["IfFalseAction"])

    def test_ipv6_url(self):
        config = configuration()
        config["servers"][0]["address"] = "::1"
        self.assertEqual(parse(config)["VM1Source"]["URL"], "http://[::1]:5000/stats")

    def test_validation(self):
        for field, value in (("host_title", "[!Execute]"), ("scale", 0), ("scale", float("nan")), ("update_seconds", 0)):
            config = configuration()
            config[field] = value
            with self.assertRaises(ValueError):
                generator.render(config)
        config = configuration(2)
        config["servers"][1]["id"] = "vm0"
        with self.assertRaises(ValueError):
            generator.render(config)
        config = configuration()
        config["servers"][0]["address"] = "127.0.0.1/path"
        with self.assertRaises(ValueError):
            generator.render(config)

    def test_all_twenty_variants_share_one_config_and_have_exact_capacity(self):
        config = configuration(10)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ServerStats" / "Aggregate" / "Aggregate.ini"
            generator.generate_all(config, output)
            self.assertEqual(len(list(output.parent.glob("*.ini"))), 21)  # 20 fixed + auto
            common = output.parent.parent / "@Resources" / "Aggregate" / "servers.inc"
            shared = configparser.RawConfigParser()
            shared.read(common, encoding="utf-16")
            self.assertEqual(shared["Variables"]["VM1Address"], "192.168.1.1")
            self.assertEqual(shared["Variables"]["HostTitle"], "HOST-01")
            for slots in range(1, 21):
                variant = output.with_name(f"Aggregate-{slots:02d}.ini")
                content = variant.read_text(encoding="utf-16")
                skin = configparser.RawConfigParser()
                skin.read_string(content)
                self.assertEqual(skin["Variables"]["@Include"], "#@#Aggregate\\servers.inc")
                self.assertNotIn("192.168.1.", content)
                self.assertEqual(skin["Title"]["Text"], "#HostTitle#")
                self.assertIn(f",{72+min(slots,10)*88-2},8", skin["Background"]["Shape"])
                configured = min(slots, 10)
                self.assertEqual(skin["Count"]["Text"], f"{configured}/{slots} VM")
                sources = [s for s in skin.sections() if re.fullmatch(r"VM\d+Source", s)]
                self.assertEqual(len(sources), configured)
                for i in range(1, configured+1):
                    self.assertEqual(skin[f"VM{i}Source"]["URL"], f"http://#VM{i}URLHost#:#VM{i}Port#/#VM{i}StatsPath#")
                for i in range(configured+1, slots+1):
                    self.assertIn(f"VM{i}Empty", skin)
                    self.assertNotIn(f"VM{i}Source", skin)
            config["servers"].append({"id": "new", "address": "::1", "port": 5050})
            generator.generate_all(config, output)
            shared.read(common, encoding="utf-16")
            self.assertEqual(shared["Variables"]["VM11URLHost"], "[::1]")
            self.assertEqual(shared["Variables"]["VM11Port"], "5050")
            skin = configparser.RawConfigParser()
            skin.read(output.with_name("Aggregate-11.ini"), encoding="utf-16")
            self.assertIn("VM11Source", skin)
            self.assertNotIn("VM11Empty", skin)

    def test_demo_paths_are_shared_and_wire_format_matches(self):
        import server_stats
        config = configuration(4)
        for server, load in zip(config["servers"], (10, 50, 80, 100)):
            server["demo_load"] = load
        common = configparser.RawConfigParser()
        common.read_string(generator.render_shared_variables(config))
        skin = parse(config)
        for i, load in enumerate((10, 50, 80, 100), 1):
            self.assertEqual(common["Variables"][f"VM{i}StatsPath"], f"demo/{load}")
            self.assertTrue(skin[f"VM{i}Source"]["URL"].endswith(f"/demo/{load}"))
            response = server_stats.app.test_client().get(f"/demo/{load}").get_data(as_text=True)
            self.assertIsNotNone(re.fullmatch(skin[f"VM{i}Source"]["RegExp"], response))
        self.assertEqual(generator.stats_path({}), "stats")
        for invalid in (0, 11, 100.0, "80", True):
            config["servers"][0]["demo_load"] = invalid
            with self.assertRaises(ValueError):
                generator.render(config)

    def test_variants_use_enabled_server_order_and_support_empty_config(self):
        config = configuration(3)
        config["servers"][0]["enabled"] = False
        shared = generator.render_shared_variables(config)
        self.assertIn("VM1Address=192.168.1.2", shared)
        self.assertNotIn("192.168.1.1", shared)
        skin = configparser.RawConfigParser()
        skin.read_string(generator.render(configuration(0), slots=20, shared=True))
        self.assertIn("VM20Empty", skin)
        self.assertFalse(any(s.endswith("Source") for s in skin.sections()))
        for slots in (0, 21):
            with self.assertRaises(ValueError):
                generator.render(config, slots=slots)

    def test_refresh_uses_installed_folder_name(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "Rainmeter.exe"
            exe.touch()
            installed = Path(directory) / "ServerStats 2.0" / "Aggregate" / "Aggregate.ini"
            with patch.object(generator, "SKIN_PATH", installed), \
                    patch.object(generator.shutil, "which", return_value=str(exe)), \
                    patch.object(generator.subprocess, "run") as run:
                generator.refresh()
            run.assert_called_once_with([str(exe), "!Refresh", "ServerStats 2.0\\Aggregate"], check=True)

    def test_utf16_output_and_scale(self):
        config = configuration(10)
        config["scale"] = 0.8
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Aggregate.ini"
            generator.generate(config, target)
            self.assertTrue(target.read_bytes().startswith(b"\xff\xfe"))
            self.assertIn("Text=CPU", target.read_text(encoding="utf-16"))
            self.assertIn("Rectangle 1,1,661,760,8", target.read_text(encoding="utf-16"))


if __name__ == "__main__":
    unittest.main()
