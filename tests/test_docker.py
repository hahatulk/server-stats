import importlib.util
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DockerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("docker"), "Docker CLI is not installed")
    def test_compose_linux_and_desktop_network_modes(self):
        env = dict(os.environ)
        env.update(SERVER_STATS_HOST="127.0.0.1", SERVER_STATS_PORT="5005",
                   SERVER_STATS_PUBLISH_HOST="127.0.0.1", SERVER_STATS_PUBLISH_PORT="15005")
        env.pop("COMPOSE_PROFILES", None)
        def config(profile=None):
            command = ["docker", "compose", "-f", str(ROOT / "compose.yaml")]
            if profile:
                command.extend(["--profile", profile])
            result = subprocess.run(command + ["config", "--format", "json"],
                                    capture_output=True, text=True, encoding="utf-8", check=True, timeout=20, env=env)
            return json.loads(result.stdout)["services"]
        default_services = config()
        self.assertEqual(set(default_services), {"server-stats"})
        linux = config("linux")["server-stats-linux"]
        self.assertEqual(linux["network_mode"], "host")
        self.assertFalse(linux.get("ports"))
        desktop = default_services["server-stats"]
        self.assertEqual(desktop["network_mode"], "bridge")
        self.assertEqual(desktop["environment"]["SERVER_STATS_HOST"], "0.0.0.0")
        port = desktop["ports"][0]
        self.assertEqual(port["host_ip"], "127.0.0.1")
        self.assertEqual(str(port["published"]), "15005")
        self.assertEqual(port["target"], 5005)

    def test_gunicorn_starts_collector_in_worker(self):
        with patch.dict(os.environ, {"SERVER_STATS_HOST": "127.0.0.1", "SERVER_STATS_PORT": "5050"}):
            config = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
        self.assertEqual(config["workers"], 1)
        self.assertEqual(config["threads"], 4)
        self.assertEqual(config["bind"], "127.0.0.1:5050")
        self.assertFalse(config["preload_app"])
        with patch("threading.Thread") as thread:
            config["post_worker_init"](None)
        thread.assert_called_once()
        self.assertTrue(thread.call_args.kwargs["daemon"])
        self.assertEqual(thread.call_args.kwargs["target"].__name__, "stats_collector")
        thread.return_value.start.assert_called_once()

    def test_linux_procfs_override_before_sampling(self):
        import psutil

        with patch.object(psutil, "PROCFS_PATH", "/proc", create=True), \
                patch.dict(os.environ, {"SERVER_STATS_PROCFS": "/host/proc"}), patch("os.name", "posix"):
            spec = importlib.util.spec_from_file_location("server_stats_docker_test", ROOT / "server_stats.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(psutil.PROCFS_PATH, "/host/proc")

    def test_windows_ignores_procfs_override(self):
        import psutil

        with patch.object(psutil, "PROCFS_PATH", "/proc", create=True), \
                patch.dict(os.environ, {"SERVER_STATS_PROCFS": "/host/proc"}), patch("os.name", "nt"):
            spec = importlib.util.spec_from_file_location("server_stats_windows_test", ROOT / "server_stats.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(psutil.PROCFS_PATH, "/proc")


if __name__ == "__main__":
    unittest.main()
