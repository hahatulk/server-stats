"""Regression checks for the screenshot-inspired Rainmeter layout."""
import configparser
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "ServerStats/@Resources/Aggregate/generate.py"
spec = importlib.util.spec_from_file_location("aggregate_generate_modern_tests", SCRIPT)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def config(count=1):
    return {
        "host_title": "VMs",
        "update_seconds": 2,
        "servers": [
            {"id": f"vm{i}", "address": f"192.168.1.{i+10}", "name": f"pc-{i}"}
            for i in range(1, count + 1)
        ],
    }


def skin(settings, *, slots=None, shared=False):
    ini = configparser.RawConfigParser(strict=True)
    ini.read_string(generator.render(settings, slots=slots, shared=shared))
    return ini


class ModernLayoutTests(unittest.TestCase):
    def test_looks_like_reference_card(self):
        panel = skin(config())
        self.assertIn("Rectangle 0,0,820,100", panel["Background"]["Shape"])
        self.assertIn("Rectangle 0,0,818,98,12", panel["VM1Card"]["Shape"])
        self.assertEqual(panel["VM1Card"]["X"], "1")
        self.assertEqual(panel["VM1Card"]["Y"], "1")
        self.assertIn("#BackgroundColor#", panel["VM1Card"]["Shape"])
        self.assertEqual(panel["Variables"]["BackgroundColor"], "10,14,32,252")
        self.assertEqual(panel["VM1Name"]["Text"], "pc-1")
        self.assertEqual(panel["VM1Name"]["X"], "28")
        self.assertEqual(panel["VM1HostnameText"]["MeasureName"], "VM1Hostname")
        self.assertEqual(panel["VM1Status"]["Text"], "Онлайн · интервал 2 с")
        self.assertEqual(panel["Variables"]["VM1NetUnit"], "Кбит/с")
        self.assertEqual(panel["VM1CPUValue"]["X"], "199")
        self.assertEqual(panel["VM1RAMValue"]["X"], "325")
        self.assertEqual(panel["VM1NetValue"]["X"], "451")
        self.assertEqual(panel["VM1DiskIO"]["X"], "577")
        for suffix, x in (("CPUGraph", 199), ("RAMGraph", 325),
                          ("NetGraph", 451), ("DiskIOGraph", 577)):
            self.assertEqual(panel["VM1" + suffix + "Frame"]["X"], str(x))
            self.assertEqual(panel["VM1" + suffix + "Frame"]["Y"], "49")
            self.assertIn("110,38,5", panel["VM1" + suffix + "Frame"]["Shape"])

    def test_caption_positions_and_16_pixel_graph_gaps(self):
        # The labels and graphs must share the same left edge on both panels.
        for i in (1, 11, 20):
            panel = skin(config(20))
            prefix = f"VM{i}"
            offset = 836 if i > 10 else 0
            plots = [
                ("CPUValue", "CPUGraph", 199),
                ("RAMValue", "RAMGraph", 325),
                ("NetValue", "NetGraph", 451),
                ("DiskIO", "DiskIOGraph", 577),
            ]
            for caption, plot, x in plots:
                label = panel[prefix + caption]
                frame = panel[prefix + plot + "Frame"]
                self.assertEqual(int(label["X"]), x + offset)
                self.assertEqual(int(frame["X"]), x + offset)
                self.assertEqual(label["W"], "110")
                self.assertEqual(frame["W"] if "W" in frame else
                                 frame["Shape"].split(",")[2], "110")
            for previous, following in zip(plots, plots[1:]):
                left = panel[prefix + previous[1] + "Frame"]
                right = panel[prefix + following[1] + "Frame"]
                self.assertEqual(int(right["X"]) - int(left["X"]) - 110, 16)
            self.assertEqual(panel[prefix + "NetValue"]["X"],
                             panel[prefix + "NetUpload"]["X"])
            self.assertEqual(panel[prefix + "DiskIO"]["X"],
                             panel[prefix + "DiskWriteValue"]["X"])
            self.assertEqual(panel[prefix + "CPUValue"]["Y"],
                             str(((i-1)%10)*100+47))
            bottom_aligned = ("CPUValue", "RAMValue", "NetUpload", "DiskWriteValue")
            for name in bottom_aligned:
                meter = panel[prefix + name]
                frame = panel[prefix + "CPUGraphFrame"]
                self.assertEqual(meter["StringAlign"], "LeftBottom")
                self.assertEqual(int(meter["Y"]), int(frame["Y"]) - 2)
            for name in ("NetValue", "DiskIO"):
                meter = panel[prefix + name]
                self.assertEqual(meter["StringAlign"], "LeftBottom")
                self.assertEqual(int(meter["Y"]), int(frame["Y"]) - 20)
        panel = skin(config(20))
        self.assertEqual(int(panel["VM11Card"]["X"]) -
                         (int(panel["VM1Card"]["X"]) + 818 + 2), 16)

    def test_live_graphs_network_disks_and_ring(self):
        panel = skin(config())
        for metric in ("CPU", "RAM", "Disk"):
            self.assertEqual(panel["VM1" + metric]["MaxValue"], "100")
        for suffix in ("CPUGraph", "RAMGraph", "NetGraph", "DiskIOGraph"):
            graph = panel["VM1" + suffix]
            self.assertEqual(graph["Meter"], "Line")
            self.assertEqual(graph["UpdateDivider"], "2")
            self.assertEqual(graph["W"], "103")
            self.assertEqual(graph["H"], "32")
            self.assertEqual(graph["Group"], "VM1Data")
        self.assertEqual(panel["VM1NetGraph"]["LineCount"], "2")
        self.assertEqual(panel["VM1NetGraph"]["LineColor"], "#NetColor#")
        self.assertEqual(panel["VM1NetGraph"]["LineColor2"], "#UploadColor#")
        self.assertEqual(panel["VM1DiskIOGraph"]["MeasureName"], "VM1DiskRead")
        self.assertEqual(panel["VM1DiskIOGraph"]["MeasureName2"], "VM1DiskWrite")
        self.assertEqual(panel["VM1DiskIOGraph"]["LineCount"], "2")
        self.assertEqual(panel["VM1DiskPie"]["Meter"], "Roundline")
        self.assertEqual(panel["VM1DiskPie"]["LineStart"], "21")
        self.assertEqual(panel["VM1DiskPie"]["LineLength"], "29")
        self.assertEqual(panel["VM1DiskPieBackground"]["MeasureName"], "VM1DiskTrack")
        self.assertEqual(panel["VM1DiskPercent"]["MeasureName"], "VM1Disk")
        self.assertEqual(panel["VM1DiskDetail"]["Text"], "%1 / %2 ГБ")
        self.assertEqual(panel["VM1DiskIO"]["Text"], "R %1 MB/s")
        self.assertEqual(panel["VM1DiskWriteValue"]["Text"], "W %1 MB/s")
        for meter, font_size in (("CPUValue", 8), ("RAMValue", 8),
                                 ("NetValue", 8), ("NetUpload", 8),
                                 ("DiskIO", 8), ("DiskWriteValue", 8),
                                 ("DiskPercent", 7), ("DiskDetail", 8)):
            self.assertEqual(panel["VM1" + meter]["FontSize"], str(font_size))
        self.assertEqual(panel["VM1DiskPercent"]["Y"], "36")
        self.assertEqual(panel["VM1DiskPercent"]["H"], "60")
        self.assertEqual(panel["VM1DiskPercent"]["X"], "758")
        self.assertEqual(panel["VM1DiskPercent"]["StringAlign"], "CenterCenter")
        self.assertEqual(panel["VM1DiskDetail"]["X"], "758")

    def test_vm_identification_column_does_not_change(self):
        panel = skin(config())
        for suffix, x, y, width, font_size in (
            ("Name", 28, 7, 148, 11),
            ("Address", 28, 33, 148, 10),
            ("HostnameText", 28, 33, 148, 10),
            ("Waiting", 28, 63, 148, 9),
            ("Offline", 28, 63, 148, 9),
            ("Status", 28, 63, 148, 9),
        ):
            meter = panel["VM1" + suffix]
            self.assertEqual(int(meter["X"]), x)
            self.assertEqual(int(meter["Y"]), y)
            self.assertEqual(int(meter["W"]), width)
            self.assertEqual(int(meter["FontSize"]), font_size)
        self.assertEqual(panel["VM1DotWaiting"]["X"], "14")
        self.assertEqual(panel["VM1DotWaiting"]["Y"], "15")

    def test_offline_state_and_warning_colors(self):
        panel = skin(config())
        self.assertIn("!HideMeterGroup VM1Data",
                      panel["VM1Connection"]["IfTrueAction2"])
        self.assertIn("!ShowMeterGroup VM1Data",
                      panel["VM1Connection"]["IfTrueAction"])
        self.assertEqual(panel["VM1Source"]["FinishAction"],
                         "[!SetVariable VM1Online 1]")
        self.assertEqual(panel["VM1Source"]["UpdateRate"], "2")
        self.assertEqual(panel["VM1CPUGraph"]["Hidden"], "1")
        self.assertEqual(panel["VM1Status"]["Hidden"], "1")
        for metric in ("CPU", "RAM", "Disk"):
            condition = panel["VM1" + metric + "Warning"]
            self.assertEqual(condition["IfCondition"], f"(VM1{metric} >= 80)")
            self.assertIn("#WarningColor#", condition["IfTrueAction"])
        self.assertIn("VM1DiskPie LineColor",
                      panel["VM1DiskWarning"]["IfTrueAction"])

    def test_column_and_slot_geometry(self):
        for count in (1, 10, 11, 20):
            panel = skin(config(count))
            if count <= 10:
                self.assertIn(f"820,{count * 100}", panel["Background"]["Shape"])
            else:
                self.assertIn(f"1656,{max(10, count - 10) * 100}",
                              panel["Background"]["Shape"])
                self.assertEqual(int(panel["VM11Name"]["X"]) -
                                 int(panel["VM1Name"]["X"]), 836)
                self.assertEqual(panel["VM11Name"]["Y"], panel["VM1Name"]["Y"])
            self.assertEqual(panel[f"VM{count}Source"]["UpdateRate"], "2")
        panel = skin(config(1), slots=12, shared=True)
        self.assertIn("VM12EmptyCard", panel)
        self.assertIn("VM12Empty", panel)
        self.assertEqual(panel["VM11EmptyCard"]["X"], "837")
        self.assertEqual(panel["VM1Name"]["Text"], "#VM1Name#")
        self.assertEqual(panel["Variables"]["@Include"],
                         "#@#Aggregate\\servers.inc")

    def test_fullhd_two_column_bounds(self):
        panel = skin(config(20))
        self.assertIn("Rectangle 0,0,1656,1000", panel["Background"]["Shape"])
        for i in range(1, 21):
            prefix = f"VM{i}"
            offset = 836 if i > 10 else 0
            row_y = ((i - 1) % 10) * 100
            card = panel[prefix + "Card"]
            self.assertEqual(int(card["X"]), offset + 1)
            self.assertEqual(int(card["Y"]), row_y + 1)
            self.assertIn("818,98,12", card["Shape"])
            for suffix, graph_x in (("CPUGraph", 199), ("RAMGraph", 325),
                                    ("NetGraph", 451), ("DiskIOGraph", 577)):
                graph = panel[prefix + suffix]
                frame = panel[prefix + suffix + "Frame"]
                self.assertEqual(int(frame["X"]), offset + graph_x)
                self.assertEqual(int(frame["Y"]), row_y + 49)
                self.assertLessEqual(int(graph["X"]) + int(graph["W"]), offset + 820)
                self.assertLessEqual(int(graph["Y"]) + int(graph["H"]), row_y + 100)
            ring = panel[prefix + "DiskPie"]
            self.assertEqual(int(ring["X"]), offset + 728)
            self.assertEqual(int(ring["Y"]), row_y + 6)
            self.assertLessEqual(int(ring["X"]) + int(ring["W"]), offset + 820)
            self.assertLessEqual(int(ring["Y"]) + int(ring["H"]), row_y + 100)
            detail = panel[prefix + "DiskDetail"]
            percent = panel[prefix + "DiskPercent"]
            io_frame = panel[prefix + "DiskIOGraphFrame"]
            self.assertEqual(int(ring["X"]) - (int(io_frame["X"]) + 110), 41)
            self.assertEqual(percent["StringAlign"], "CenterCenter")
            self.assertEqual(int(percent["X"]), int(ring["X"]) + int(ring["W"]) // 2)
            self.assertEqual(int(percent["Y"]), int(ring["Y"]) + int(ring["H"]) // 2)
            self.assertEqual(int(percent["X"]), int(detail["X"]))
            self.assertLessEqual(int(detail["Y"]) + int(detail["H"]), row_y + 100)

    def test_right_margin_after_disk_is_compact(self):
        panel = skin(config(20))
        for number in (1, 10, 11, 20):
            prefix = f"VM{number}"
            card = panel[prefix + "Card"]
            detail = panel[prefix + "DiskDetail"]
            ring = panel[prefix + "DiskPie"]
            card_right = int(card["X"]) + 818
            # DiskDetail uses a centered X anchor; its full box must fit.
            detail_right = int(detail["X"]) + int(detail["W"]) // 2
            self.assertEqual(card_right - detail_right, 11)
            self.assertGreater(card_right, int(ring["X"]) + int(ring["W"]))
        self.assertIn("Rectangle 0,0,1656,1000",
                      panel["Background"]["Shape"])

    def test_scale_and_legacy_layout_option_has_no_effect(self):
        settings = config()
        settings["scale"] = 0.8
        panel = skin(settings)
        self.assertIn("Rectangle 0,0,656,80", panel["Background"]["Shape"])
        # Obsolete layout options must never switch back to the old design.
        for old_value in ("classic", "modern", None):
            settings = config()
            settings["layout"] = old_value
            with self.subTest(value=old_value):
                self.assertIn("VM1Card", skin(settings))
                self.assertNotIn("ColumnCPU", skin(settings))


if __name__ == "__main__":
    unittest.main()
