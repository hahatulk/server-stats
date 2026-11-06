"""Behavioral regression tests for the single supported Rainmeter dashboard."""
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
        {"id": f"vm{i}", "address": f"192.168.1.{i+1}", "name": f"vm-{i}"}
        for i in range(count)
    ]}


def parse(config, **opts):
    ini = configparser.RawConfigParser(strict=True)
    ini.read_string(generator.render(config, **opts))
    return ini


class AggregateTests(unittest.TestCase):
    def test_single_design_always_used_even_with_legacy_option(self):
        cfg = configuration()
        expected = parse(cfg)
        cfg["layout"] = "classic"  # Old configuration cannot activate the old UI.
        actual = parse(cfg)
        self.assertEqual(expected.sections(), actual.sections())
        self.assertIn("Rectangle 0,0,818,98,12", actual["VM1Card"]["Shape"])
        self.assertEqual(actual["VM1CPUGraph"]["W"], "103")
        self.assertNotIn("ColumnCPU", actual)
        self.assertNotIn("Count", actual)

    def test_wire_format_and_all_twelve_fields(self):
        panel = parse(configuration())
        response = (
            "CPU:12.5;RAM:60.0;RAM_USED:3.0;RAM_TOTAL:5.0;"
            "NET_RECV:1.2;NET_SENT:0.3;HOSTNAME:vm-linux;"
            "DISK_PERCENT:40.0;DISK_USED:20.0;DISK_TOTAL:50.0;"
            "DISK_READ:12.5;DISK_WRITE:3.2"
        )
        match = re.search(panel["VM1Source"]["RegExp"], response)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("12.5", "60.0", "3.0", "5.0",
                                         "1.2", "0.3", "vm-linux", "40.0",
                                         "20.0", "50.0", "12.5", "3.2"))
        self.assertIsNone(re.search(panel["VM1Source"]["RegExp"],
                                    response.split(";DISK_READ")[0]))
        for index, field in enumerate(("CPU", "RAM", "RAMUsed", "RAMTotal",
                                        "Recv", "Sent", "Hostname", "Disk",
                                        "DiskUsed", "DiskTotal", "DiskRead",
                                        "DiskWrite"), 1):
            self.assertEqual(panel[f"VM1{field}"]["StringIndex"], str(index))

    def test_disabled_rows_are_not_polled(self):
        cfg = configuration(3)
        cfg["servers"][1]["enabled"] = False
        panel = parse(cfg)
        self.assertEqual(panel["VM2Source"]["URL"],
                         "http://192.168.1.3:5000/stats")
        self.assertNotIn("VM3Source", panel)

    def test_offline_recovery_and_slow_retry(self):
        cfg = configuration()
        cfg["update_seconds"] = 60
        panel = parse(cfg)
        source = panel["VM1Source"]
        self.assertEqual(source["UpdateRate"], "60")
        self.assertEqual(source["Flags"], "ForceReload | NoCacheWrite | NoCookies")
        self.assertEqual(source["ProxyServer"], "/none")
        self.assertEqual(source["FinishAction"], "[!SetVariable VM1Online 1]")
        self.assertEqual(source["OnDownloadErrorAction"], "[!SetVariable VM1Online 0]")
        self.assertEqual(source["OnRegExpErrorAction"], "[!SetVariable VM1Online 0]")
        self.assertIn("!ShowMeterGroup VM1Data",
                      panel["VM1Connection"]["IfTrueAction"])
        self.assertIn("!HideMeterGroup VM1Data",
                      panel["VM1Connection"]["IfTrueAction2"])
        self.assertIn("!ShowMeter VM1DotOffline",
                      panel["VM1Connection"]["IfTrueAction2"])
        self.assertIn("!SetOption VM1Source UpdateRate 60",
                      panel["VM1Connection"]["IfTrueAction2"])
        self.assertEqual(panel["VM1CPUValue"]["Hidden"], "1")
        self.assertEqual(panel["VM1Offline"]["Hidden"], "1")

    def test_graph_samples_and_value_updates_match(self):
        for interval in (1, 2, 5, 60):
            cfg = configuration(11)
            cfg["update_seconds"] = interval
            panel = parse(cfg)
            self.assertEqual(panel["Rainmeter"]["Update"], "1000")
            self.assertEqual(panel["Rainmeter"]["DynamicWindowSize"], "0")
            for i in (1, 10, 11):
                p = f"VM{i}"
                self.assertEqual(panel[p+"Source"]["UpdateRate"], str(interval))
                for val, graph in (("CPUValue", "CPUGraph"), ("RAMValue", "RAMGraph"),
                                   ("NetValue", "NetGraph"), ("DiskIO", "DiskIOGraph"),
                                   ("DiskDetail", "DiskPie")):
                    self.assertEqual(panel[p+val]["UpdateDivider"], str(interval))
                    self.assertEqual(panel[p+graph]["UpdateDivider"], str(interval))
                self.assertEqual(panel[p+"CPUGraphFill"]["UpdateDivider"], str(interval))
                self.assertEqual(panel[p+"RAMGraphFill"]["UpdateDivider"], str(interval))
                self.assertEqual(panel[p+"CPUGraphFrame"]["UpdateDivider"], "-1")
                self.assertEqual(panel[p+"Card"]["UpdateDivider"], "-1")
            output = generator.render(cfg)
            self.assertNotIn("!UpdateMeter *", output)
            self.assertNotIn("!Redraw", output)

    def test_network_adaptive_units(self):
        panel = parse(configuration())
        self.assertEqual(panel["Variables"]["VM1NetUnit"], "Кбит/с")
        self.assertEqual(panel["VM1NetPeak"]["Formula"], "Max(VM1Recv, VM1Sent)")
        self.assertEqual(panel["VM1NetScale"]["Formula"],
                         "(VM1NetPeak >= 1000 ? 1000 : (VM1NetPeak >= 1 ? 1 : 0.001))")
        for suffix, unit in (("", "Кбит/с"), ("2", "Мбит/с"), ("3", "Гбит/с")):
            self.assertEqual(panel["VM1NetScale"]["IfTrueAction"+suffix],
                             f'[!SetVariable VM1NetUnit "{unit}"]')
        for direction in ("Recv", "Sent"):
            self.assertEqual(panel["VM1Net"+direction+"Display"]["Formula"],
                             f"Round(VM1{direction} / VM1NetScale, 1)")
        self.assertEqual(panel["VM1NetValue"]["MeasureName"], "VM1NetRecvDisplay")
        self.assertEqual(panel["VM1NetUpload"]["MeasureName"], "VM1NetSentDisplay")
        self.assertEqual(panel["VM1NetGraph"]["AutoScale"], "1")
        self.assertEqual(panel["VM1NetGraph"]["LineCount"], "2")

    def test_disk_and_warning_thresholds(self):
        panel = parse(configuration())
        self.assertEqual(panel["VM1DiskDetail"]["MeasureName"], "VM1DiskUsed")
        self.assertEqual(panel["VM1DiskDetail"]["MeasureName2"], "VM1DiskTotal")
        self.assertEqual(panel["VM1DiskIOGraph"]["MeasureName"], "VM1DiskRead")
        self.assertEqual(panel["VM1DiskIOGraph"]["MeasureName2"], "VM1DiskWrite")
        self.assertEqual(panel["VM1DiskPie"]["LineColor"], "#PieColor#")
        for metric, target in (("CPU", "CPUValue"),
                               ("RAM", "RAMValue"), ("Disk", "DiskDetail")):
            warning = panel["VM1"+metric+"Warning"]
            self.assertEqual(warning["IfCondition"], f"(VM1{metric} >= 80)")
            self.assertIn(f'VM1{target} FontColor "#WarningColor#"',
                          warning["IfTrueAction"])
        self.assertIn('VM1DiskPie LineColor "#PieColor#"',
                      panel["VM1DiskWarning"]["IfFalseAction"])

    def test_two_columns_and_empty_slots(self):
        for count in (0, 1, 10, 11, 20):
            panel = parse(configuration(count))
            visible = min(count, 20)
            self.assertEqual(len([name for name in panel.sections()
                                  if re.fullmatch(r"VM\d+Source", name)]), visible)
            self.assertEqual(panel["Background"]["UpdateDivider"], "-1")
            if count == 0:
                self.assertIn("VM1Empty", parse(configuration(0), slots=1))
            if count > 10:
                self.assertEqual(int(panel["VM11Card"]["X"]) -
                                 int(panel["VM1Card"]["X"]), 836)
                self.assertEqual(panel["VM11Card"]["Y"], panel["VM1Card"]["Y"])
        fixed = parse(configuration(1), slots=20, shared=True)
        self.assertIn("VM20EmptyCard", fixed)
        self.assertEqual(fixed["VM20EmptyCard"]["X"], "837")
        self.assertNotIn("VM2Source", fixed)

    def test_shared_config_and_all_skins(self):
        cfg = configuration(2)
        cfg["servers"][1]["port"] = 5050
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ServerStats" / "Aggregate" / "Aggregate.ini"
            generator.generate_all(cfg, target)
            self.assertEqual(len(list(target.parent.glob("*.ini"))), 21)
            common = target.parent.parent / "@Resources" / "Aggregate" / "servers.inc"
            variables = configparser.RawConfigParser()
            variables.read(common, encoding="utf-16")
            self.assertEqual(variables["Variables"]["VM2Port"], "5050")
            for number in range(1, 21):
                panel = configparser.RawConfigParser()
                panel.read(target.with_name(f"Aggregate-{number:02d}.ini"),
                           encoding="utf-16")
                self.assertEqual(panel["Variables"]["@Include"],
                                 "#@#Aggregate\\servers.inc")
                self.assertEqual(panel["VM1Name"]["Text"], "#VM1Name#")
                self.assertNotIn("192.168.1.", panel["VM1Source"]["URL"])
                self.assertEqual(panel["VM1Source"]["URL"],
                                 "http://#VM1URLHost#:#VM1Port#/#VM1StatsPath#")
                self.assertEqual("VM2Source" in panel, number > 1)
                self.assertIn("VM20EmptyCard", panel) if number == 20 else None

    def test_demo_routes_and_ipv6(self):
        cfg = configuration()
        cfg["servers"][0].update(address="::1", demo_load=80)
        panel = parse(cfg)
        self.assertEqual(panel["VM1Source"]["URL"], "http://[::1]:5000/demo/80")
        shared = generator.render_shared_variables(cfg)
        self.assertIn("VM1URLHost=[::1]", shared)
        self.assertIn("VM1StatsPath=demo/80", shared)
        import server_stats
        response = server_stats.app.test_client().get("/demo/80").get_data(as_text=True)
        self.assertIsNotNone(re.fullmatch(panel["VM1Source"]["RegExp"], response))
        self.assertEqual(generator.stats_path({}), "stats")
        for invalid in (0, "80", True, 80.0):
            cfg["servers"][0]["demo_load"] = invalid
            with self.assertRaises(ValueError):
                generator.render(cfg)

    def test_validation(self):
        cases = (("host_title", "[!Execute]"),
                 ("scale", float("nan")), ("scale", 0),
                 ("scale", 3), ("update_seconds", 0))
        for key, value in cases:
            cfg = configuration()
            cfg[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                generator.render(cfg)
        cfg = configuration(2)
        cfg["servers"][1]["id"] = "vm0"
        with self.assertRaises(ValueError):
            generator.render(cfg)
        cfg = configuration()
        cfg["servers"][0]["address"] = "localhost/path"
        with self.assertRaises(ValueError):
            generator.render(cfg)
        for slots in (0, 21):
            with self.assertRaises(ValueError):
                generator.render(configuration(), slots=slots)

    def test_utf16_and_scale(self):
        cfg = configuration()
        cfg["scale"] = 0.8
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "Aggregate.ini"
            generator.generate(cfg, output)
            self.assertTrue(output.read_bytes().startswith(b"\xff\xfe"))
            content = output.read_text(encoding="utf-16")
            self.assertIn("Rectangle 0,0,656,80", content)
            self.assertIn("Text=%1%", content)

    def test_refresh_uses_installed_folder_name(self):
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "Rainmeter.exe"
            exe.touch()
            installed = (Path(directory) / "ServerStats 2.0" /
                         "Aggregate" / "Aggregate.ini")
            with patch.object(generator, "SKIN_PATH", installed), \
                 patch.object(generator.shutil, "which", return_value=str(exe)), \
                 patch.object(generator.subprocess, "run") as run:
                generator.refresh()
            run.assert_called_once_with(
                [str(exe), "!Refresh", "ServerStats 2.0\\Aggregate"], check=True)


if __name__ == "__main__":
    unittest.main()
