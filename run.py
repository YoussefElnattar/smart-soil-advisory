"""One-command launcher:  python run.py

Creates .venv on first run, installs requirements, then starts the web app at
http://127.0.0.1:8000  (API docs at /docs).

Options:
  python run.py --host 0.0.0.0 --port 8000   # expose on the LAN so a real ESP32 node can post
  python run.py --test                       # run the automated test suite
  python run.py --hardware-pdf               # regenerate docs/Hardware_BOM_Wiring_Firmware.pdf
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
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
    args = ap.parse_args()
    ensure_venv()
    backend = ROOT / "backend"
    if args.test:
        sys.exit(subprocess.call([str(PY), "-m", "pytest", "-q", str(ROOT / "tests")], cwd=backend))
    if args.hardware_pdf:
        sys.exit(subprocess.call([str(PY), "-c",
                                  "from app.services.hardware_pdf import write_default_pdf; print(write_default_pdf())"],
                                 cwd=backend))
    print(f"\n  Smart Soil Advisory Platform → http://{args.host}:{args.port}   (API docs: /docs)\n")
    sys.exit(subprocess.call([str(PY), "-m", "uvicorn", "app.main:app", "--host", args.host, "--port", args.port],
                             cwd=backend))


if __name__ == "__main__":
    main()
