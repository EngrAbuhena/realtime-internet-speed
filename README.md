# Real-Time Internet Speed

A lightweight Linux terminal dashboard for **live network traffic throughput**. It displays current receive/download and send/upload rates, traffic totals since the monitor started, and simple bar graphs.

**Important:** This measures traffic currently passing through a network interface, **not** your connection's maximum speed. It does not generate test traffic; an idle connection can read 0 Mbps. The counters include all traffic on the selected interface, not just internet traffic.

## Requirements

- Linux (including Ubuntu) with `/proc/net/dev` and the usual `/proc/net/route` or `/proc/net/ipv6_route` files
- Python 3.10 or newer
- A terminal capable of displaying Unicode for the best appearance
- No third-party Python packages

## Run

```bash
python realtime_internet_speed.py
```

Stop with **Ctrl+C**. The monitor automatically chooses an interface from the lowest-metric default IPv4/IPv6 route. To select one manually, edit `INTERFACE = ""` near the top of the file, e.g. `INTERFACE = "wlan0"`. Find your interface name with `ip link` or `ls /sys/class/net`.

Other editable constants near the top:

- `SAMPLE_INTERVAL_SECONDS` — polling interval in seconds; must be positive (default: 1)
- `BAR_SCALE_MBPS` — Mbps value that fills each bar (default: 100)
- `BAR_WIDTH` — bar length in characters

Totals count bytes received/sent during completed samples, starting after the initial baseline read. Rates use **decimal** units (1 Mbps = 1,000,000 bits/s; 1 MB = 1,000,000 bytes). The display refreshes in-place when stdout is a terminal; color can be disabled with `NO_COLOR=1`.

## Tests

The unit tests use fake `/proc` contents and mocked counters. They never consume live network traffic:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs these tests on pushes and pull requests.

## Upload to GitHub

Create an empty GitHub repository. Upload the **contents** of this folder, including `.github`, through **Add file → Upload files**, or push using Git:

```bash
cd realtime-internet-speed
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Replace the example URL with your repository URL. Set your Git name/email and authenticate with GitHub if prompted.

No license is included; choose one before inviting reuse or contributions.
