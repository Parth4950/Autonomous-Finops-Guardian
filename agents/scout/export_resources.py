"""Discover live AWS resources and export ML pipeline inputs."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.scout.resource_exporter import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
