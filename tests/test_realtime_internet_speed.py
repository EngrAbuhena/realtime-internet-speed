"""Offline tests for the Linux throughput dashboard."""

import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import TestCase, mock

script = Path(__file__).resolve().parents[1] / "realtime_internet_speed.py"
spec = importlib.util.spec_from_file_location("realtime_internet_speed", script)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(TestCase):
    def test_read_interface_counters(self):
        contents = "header\nheader\n  lo: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n"
        with mock.patch.object(monitor.Path, "read_text", return_value=contents):
            self.assertEqual(monitor.read_interface_counters(), {"lo": (100, 200)})

    def test_default_route_prefers_lower_metric(self):
        route = ("Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
                 "eth0 00000000 00000000 0003 0 0 200 00000000 0 0 0\n"
                 "wlan0 00000000 00000000 0003 0 0 100 00000000 0 0 0\n")
        def read_text(path, **_kwargs):
            if str(path).endswith("/proc/net/route"):
                return route
            raise OSError("no IPv6 route")
        with mock.patch.object(monitor.Path, "read_text", read_text):
            self.assertEqual(monitor.default_route_interface(), "wlan0")

    def test_missing_routes(self):
        with mock.patch.object(monitor.Path, "read_text", side_effect=OSError("missing")):
            self.assertIsNone(monitor.default_route_interface())

    def test_formatting_and_bars(self):
        self.assertEqual(monitor.format_rate(0.5), "500.0 Kbps")
        self.assertEqual(monitor.format_rate(2), "2.00 Mbps")
        self.assertEqual(monitor.draw_bar(-1), "░" * monitor.BAR_WIDTH)
        self.assertEqual(monitor.draw_bar(1000), "█" * monitor.BAR_WIDTH)

    def test_rejects_invalid_interval(self):
        with mock.patch.object(monitor, "SAMPLE_INTERVAL_SECONDS", 0), \
             redirect_stderr(io.StringIO()) as error:
            self.assertEqual(monitor.main(), 1)
        self.assertIn("greater than zero", error.getvalue())

    def test_reports_missing_interface(self):
        with mock.patch.object(monitor, "INTERFACE", "missing"), \
             mock.patch.object(monitor, "read_interface_counters", return_value={"eth0": (0, 0)}), \
             redirect_stderr(io.StringIO()) as error:
            self.assertEqual(monitor.main(), 1)
        self.assertIn("was not found", error.getvalue())

    def test_samples_rates_without_live_traffic(self):
        with mock.patch.object(monitor, "INTERFACE", "eth0"), \
             mock.patch.object(monitor, "read_interface_counters", side_effect=[
                 {"eth0": (100, 200)}, {"eth0": (1_000_100, 500_200)}]), \
             mock.patch.object(monitor.time, "monotonic", side_effect=[10, 11]), \
             mock.patch.object(monitor.time, "sleep", side_effect=[None, KeyboardInterrupt]), \
             mock.patch.object(monitor, "print_dashboard") as dashboard, \
             redirect_stdout(io.StringIO()):
            self.assertEqual(monitor.main(), 0)
        dashboard.assert_called_once_with("eth0", 8.0, 4.0, 1_000_000, 500_000, 1.0)
