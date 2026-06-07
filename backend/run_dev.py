"""Run the FastAPI dev server without reloading on pipeline CSV/JSON writes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--reload-dir",
        str(PROJECT_ROOT / "backend"),
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    return subprocess.call(command, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
