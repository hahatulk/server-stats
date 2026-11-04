import unittest
from types import SimpleNamespace
from unittest.mock import patch

import server_stats


class ServerStatsTests(unittest.TestCase):
    def setUp(self):
        self.client = server_stats.app.test_client()

    def test_legacy_fields_are_first_six_and_new_fields_follow(self):
        with server_stats._STATS_LOCK:
            server_stats.current_stats.update({
                "cpu": 1, "ram_percent": 2, "ram_used_gb": 3,
                "ram_total_gb": 4, "net_recv_mbps": 5, "net_sent_mbps": 6,
                "hostname": "test-host", "disk_percent": 7,
                "disk_used_gb": 8, "disk_total_gb": 9,
                "disk_read_mbps": 12.5, "disk_write_mbps": 3.2,
            })
        body = self.client.get("/stats").get_data(as_text=True)
        fields = body.split(";")
        self.assertEqual(fields[:6], [
            "CPU:1", "RAM:2", "RAM_USED:3", "RAM_TOTAL:4",
            "NET_RECV:5", "NET_SENT:6",
        ])
        self.assertEqual(fields[6:], [
            "HOSTNAME:test-host", "DISK_PERCENT:7", "DISK_USED:8",
            "DISK_TOTAL:9", "DISK_READ:12.5", "DISK_WRITE:3.2",
        ])

    def test_small_network_rates_keep_kilobit_precision_and_decimal_wire_format(self):
        with patch.object(server_stats, "_disk_stats", return_value=(50, 2, 4)), \
                patch.object(server_stats.psutil, "virtual_memory", return_value=SimpleNamespace(percent=25, used=2**30, total=4*2**30)), \
                patch.object(server_stats.psutil, "cpu_percent", return_value=10), \
                patch.object(server_stats.psutil, "disk_io_counters", return_value=None), \
                patch.object(server_stats.psutil, "net_io_counters", return_value=SimpleNamespace(bytes_recv=1, bytes_sent=125)):
            sample, _, _, _ = server_stats._collect_once(SimpleNamespace(bytes_recv=0, bytes_sent=0), None, 0, now=1)
        self.assertEqual(sample["net_recv_mbps"], 0.000008)
        self.assertEqual(sample["net_sent_mbps"], 0.001)
        with patch.object(server_stats, "_snapshot", return_value=sample):
            body = self.client.get("/stats").get_data(as_text=True)
        self.assertIn("NET_RECV:0.000008;NET_SENT:0.001;", body)
        self.assertEqual(server_stats._format_network_rate(0), "0")

    def test_demo_routes_cover_all_loads_without_changing_real_stats(self):
        before = server_stats._snapshot()
        for load in (10, 50, 80, 100):
            with self.subTest(load=load):
                response = self.client.get(f"/demo/{load}")
                self.assertEqual(response.status_code, 200)
                payload = self.client.get(f"/api/demo/{load}").get_json()
                self.assertEqual(response.get_data(as_text=True), server_stats._format_stats(payload))
                for field in ("cpu", "ram_percent", "disk_percent", "net_recv_mbps", "net_sent_mbps", "disk_read_mbps", "disk_write_mbps"):
                    self.assertEqual(payload[field], float(load))
                self.assertEqual(payload["hostname"], f"DEMO-{load}")
                self.assertEqual(payload["ram_used_gb"], round(16*load/100, 1))
                self.assertEqual(payload["disk_used_gb"], round(256*load/100, 1))
                self.assertEqual(self.client.get(f"/api/demo/{load}").get_json(), payload)
        self.assertEqual(server_stats._snapshot(), before)
        self.assertEqual(self.client.get("/api/stats").get_json(), before)
        for load in (0, 11, 79, 101):
            for prefix in ("/demo/", "/api/demo/"):
                self.assertEqual(self.client.get(prefix+str(load)).status_code, 404)

    def test_json_endpoint_contains_resource_fields(self):
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        for key in ("hostname", "disk_percent", "disk_used_gb", "disk_total_gb",
                    "disk_read_mbps", "disk_write_mbps"):
            self.assertIn(key, payload)

    @patch.object(server_stats, "_disk_stats", return_value=(50.0, 2.0, 4.0))
    @patch.object(server_stats.psutil, "disk_io_counters")
    @patch.object(server_stats.psutil, "net_io_counters")
    @patch.object(server_stats.psutil, "virtual_memory")
    @patch.object(server_stats.psutil, "cpu_percent", return_value=12.3)
    def test_collect_rates_and_counter_reset_are_safe(
        self, _cpu, virtual_memory, net_counters, disk_counters, _disk_stats
    ):
        virtual_memory.return_value = SimpleNamespace(percent=25, used=2**30, total=4**30)
        net_counters.side_effect = [SimpleNamespace(bytes_recv=100, bytes_sent=200),
                                    SimpleNamespace(bytes_recv=50, bytes_sent=300)]
        disk_counters.side_effect = [SimpleNamespace(read_bytes=100, write_bytes=200),
                                     SimpleNamespace(read_bytes=50, write_bytes=300)]
        first_net, first_disk = net_counters(), disk_counters()
        # Counters going backwards must produce zero, not a negative rate.
        sample, _, _, _ = server_stats._collect_once(first_net, first_disk, 0.0, now=1.0)
        self.assertEqual(sample["net_recv_mbps"], 0.0)
        self.assertEqual(sample["disk_read_mbps"], 0.0)

    @patch.object(server_stats, "_disk_stats", return_value=(50.0, 2.0, 4.0))
    @patch.object(server_stats.psutil, "disk_io_counters")
    @patch.object(server_stats.psutil, "net_io_counters")
    @patch.object(server_stats.psutil, "virtual_memory")
    @patch.object(server_stats.psutil, "cpu_percent", return_value=12.3)
    def test_disk_io_uses_decimal_megabytes_per_second(
        self, _cpu, memory, net, disk, _usage
    ):
        memory.return_value = SimpleNamespace(percent=25, used=2**30, total=4*2**30)
        net.return_value = SimpleNamespace(bytes_recv=0, bytes_sent=0)
        previous = SimpleNamespace(read_bytes=100, write_bytes=200)
        disk.return_value = SimpleNamespace(read_bytes=25000100, write_bytes=6400200)
        sample, _, _, _ = server_stats._collect_once(net.return_value, previous, 10.0, now=12.0)
        self.assertEqual(sample["disk_read_mbps"], 12.5)
        self.assertEqual(sample["disk_write_mbps"], 3.2)
        disk.return_value = None
        sample, _, _, _ = server_stats._collect_once(net.return_value, None, 10.0, now=12.0)
        self.assertEqual(sample["disk_read_mbps"], 0.0)
        self.assertEqual(sample["disk_write_mbps"], 0.0)


if __name__ == "__main__":
    unittest.main()
