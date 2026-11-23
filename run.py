"""One-command launcher:  python run.py   (or double-click run.bat on Windows)

Creates .venv on first run, installs requirements, starts the web app at
http://127.0.0.1:8000 (API docs at /docs) and opens it in the browser.

Options:
  python run.py --no-browser                 # start without opening the browser
  python run.py --host 0.0.0.0 --port 8000   # expose on the LAN so a real ESP32 node can post
  python run.py --test                       # run the automated test suite
  python run.py --hardware-pdf               # regenerate docs/Hardware_BOM_Wiring_Firmware.pdf
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv() -> None:
    if not PY.exists():
        print("Creating virtual environment (.venv)…")
        venv.create(VENV, with_pip=True)
    marker = VENV / ".requirements-installed"
    req = ROOT / "requirements.txt"
    if not marker.exists() or marker.stat().st_mtime < req.stat().st_mtime:
        print("Installing requirements…")
        subprocess.check_call([str(PY), "-m", "pip", "install", "--quiet", "-r", str(req)])
        marker.touch()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default="8000")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--hardware-pdf", action="store_true")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    args = ap.parse_args()
    ensure_venv()
    backend = ROOT / "backend"
    if args.test:
        sys.exit(subprocess.call([str(PY), "-m", "pytest", "-q", str(ROOT / "tests")], cwd=backend))
    if args.hardware_pdf:
        sys.exit(subprocess.call([str(PY), "-c",
                                  "from app.services.hardware_pdf import write_default_pdf; print(write_default_pdf())"],
                                 cwd=backend))
    local_url = f"http://127.0.0.1:{args.port}"
    if port_in_use(int(args.port)):
        print(f"\n  The app is already running → opening {local_url}\n")
        if not args.no_browser:
            webbrowser.open(local_url)
        return
    print(f"\n  Smart Soil Advisory Platform → {local_url}   (API docs: /docs)")
    print("  Keep this window open while you use the app. Close it (or press Ctrl+C) to stop.\n")
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(local_url,), daemon=True).start()
    try:
        code = subprocess.call([str(PY), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", args.port],
                               cwd=backend)
    except KeyboardInterrupt:
        code = 0
    sys.exit(code)


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_when_ready(url: str, timeout_s: float = 60.0) -> None:
    """Open the browser once the server answers its health check."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/v1/health", timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
