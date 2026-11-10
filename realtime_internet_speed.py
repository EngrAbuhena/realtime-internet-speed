#!/usr/bin/env python3
"""Show live receive/download and send/upload throughput in an Ubuntu terminal.

This reads Linux network-interface byte counters. It shows current traffic in
use (so it can display 0 when the connection is idle); it does not run a speed
capacity test or generate download/upload traffic.

Run:
    python realtime_internet_speed.py

Optional: set INTERFACE below to a specific interface name (for example,
"wlan0" or "enp3s0"). Leave it empty to follow the default internet route.
Stop with Ctrl+C.
"""

import os
import sys
import time
from pathlib import Path


# Leave empty to automatically monitor the interface with the default route.
INTERFACE = ""
SAMPLE_INTERVAL_SECONDS = 1.0
BAR_SCALE_MBPS = 100.0  # Bars fill at this speed; the numeric rate stays accurate.
BAR_WIDTH = 28
BOX_WIDTH = 66

RESET = "\033[0m"
COLORS = {
    "cyan": "\033[96m",
    "green": "\033[92m",
    "magenta": "\033[95m",
    "yellow": "\033[93m",
    "dim": "\033[2m",
    "bold": "\033[1m",
}


def colorize(text: str, color: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return text
    return f"{COLORS.get(color, '')}{text}{RESET}"


def read_interface_counters() -> dict[str, tuple[int, int]]:
    """Return {interface: (received_bytes, transmitted_bytes)} from /proc/net/dev."""
    counters: dict[str, tuple[int, int]] = {}
    try:
        lines = Path("/proc/net/dev").read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise RuntimeError("Cannot read /proc/net/dev; this script is intended for Linux/Ubuntu.") from exc

    for line in lines[2:]:
        if ":" not in line:
            continue
        name, data = line.rsplit(":", 1)
        interface = name.strip()
        values = data.split()
        if interface and len(values) >= 9:
            counters[interface] = (int(values[0]), int(values[8]))
    return counters


def default_route_interface() -> str | None:
    """Find the lowest-metric active IPv4/IPv6 default-route interface."""
    candidates: list[tuple[int, str]] = []

    # IPv4 default routes: /proc/net/route fields include destination, flags, metric, iface.
    try:
        lines = Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]
        for line in lines:
            fields = line.split()
            if len(fields) < 8:
                continue
            interface, destination = fields[0], fields[1]
            flags, metric = int(fields[3], 16), int(fields[6])
            if destination == "00000000" and flags & 1:
                candidates.append((metric, interface))
    except (OSError, ValueError):
        pass

    # IPv6 default routes: destination is 32 zeroes and prefix length is 00.
    try:
        lines = Path("/proc/net/ipv6_route").read_text(encoding="ascii").splitlines()
        for line in lines:
            fields = line.split()
            if len(fields) < 10:
                continue
            destination, prefix_len = fields[0], fields[1]
            metric, flags, interface = int(fields[5], 16), int(fields[8], 16), fields[9]
            if destination == "0" * 32 and prefix_len == "00" and flags & 1:
                candidates.append((metric, interface))
    except (OSError, ValueError):
        pass

    return min(candidates)[1] if candidates else None


def draw_bar(mbps: float) -> str:
    if BAR_SCALE_MBPS <= 0:
        return "░" * BAR_WIDTH
    fraction = max(0.0, min(mbps / BAR_SCALE_MBPS, 1.0))
    filled = round(fraction * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def format_rate(mbps: float) -> str:
    """Use Kbps below 1 Mbps and Mbps otherwise."""
    if 0 < mbps < 1:
        return f"{mbps * 1000:.1f} Kbps"
    return f"{mbps:.2f} Mbps"


def print_dashboard(
    interface: str,
    download_mbps: float,
    upload_mbps: float,
    total_download: int,
    total_upload: int,
    sample_seconds: float,
) -> None:
    rows = [
        (f"Interface: {interface}", "cyan"),
        (f"Refresh: {sample_seconds:g} second(s)  |  Stop: Ctrl+C", "dim"),
        ("", "dim"),
        (f"↓ DOWNLOAD  {format_rate(download_mbps):>12}   [{draw_bar(download_mbps)}]", "green"),
        (f"↑ UPLOAD    {format_rate(upload_mbps):>12}   [{draw_bar(upload_mbps)}]", "magenta"),
        ("", "dim"),
        (f"Downloaded this session: {total_download / 1_000_000:.2f} MB", "dim"),
        (f"Uploaded this session:   {total_upload / 1_000_000:.2f} MB", "dim"),
        ("", "dim"),
        ("Live traffic rate; no test data is generated. Idle may show 0.", "yellow"),
    ]

    top = "╔" + "═" * BOX_WIDTH + "╗"
    separator = "╠" + "═" * BOX_WIDTH + "╣"
    bottom = "╚" + "═" * BOX_WIDTH + "╝"
    title = "REAL-TIME INTERNET SPEED"

    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
    print(colorize(top, "cyan"))
    print(colorize("║" + title.center(BOX_WIDTH) + "║", "bold"))
    print(colorize(separator, "cyan"))
    for text, shade in rows:
        content = text[:BOX_WIDTH].ljust(BOX_WIDTH)
        print("║" + colorize(content, shade) + "║")
    print(colorize(bottom, "cyan"))
    sys.stdout.flush()


def main() -> int:
    if SAMPLE_INTERVAL_SECONDS <= 0:
        print("SAMPLE_INTERVAL_SECONDS must be greater than zero.", file=sys.stderr)
        return 1

    previous_interface: str | None = None
    previous_counters: tuple[int, int] | None = None
    previous_time: float | None = None
    total_download = 0
    total_upload = 0

    try:
        while True:
            counters = read_interface_counters()
            interface = INTERFACE.strip() or default_route_interface()

            if not interface:
                print(
                    "Could not identify the default network interface. "
                    "Set INTERFACE near the top of the script (e.g. 'wlan0').",
                    file=sys.stderr,
                )
                return 1
            if interface not in counters:
                print(f"Interface {interface!r} was not found. Available: {', '.join(counters)}", file=sys.stderr)
                return 1

            current = counters[interface]
            if previous_interface != interface or previous_counters is None or previous_time is None:
                previous_interface = interface
                previous_counters = current
                previous_time = time.monotonic()
                time.sleep(SAMPLE_INTERVAL_SECONDS)
                continue

            now = time.monotonic()
            elapsed = max(now - previous_time, 0.001)
            received_delta = max(0, current[0] - previous_counters[0])
            transmitted_delta = max(0, current[1] - previous_counters[1])
            total_download += received_delta
            total_upload += transmitted_delta
            download_mbps = received_delta * 8 / elapsed / 1_000_000
            upload_mbps = transmitted_delta * 8 / elapsed / 1_000_000

            print_dashboard(
                interface,
                download_mbps,
                upload_mbps,
                total_download,
                total_upload,
                SAMPLE_INTERVAL_SECONDS,
            )

            previous_counters = current
            previous_time = now
            time.sleep(SAMPLE_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopped real-time monitor.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Monitor error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
