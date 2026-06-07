"""Export approval workflow data for the React dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPROVALS_PATH = _PROJECT_ROOT / "workflow" / "results" / "approvals.json"
HISTORY_PATH = _PROJECT_ROOT / "workflow" / "history" / "approval_history.json"
OUTPUT_PATH = _PROJECT_ROOT / "frontend" / "src" / "data" / "approvals-data.json"


def main() -> int:
    if not APPROVALS_PATH.exists():
        print(f"Approvals JSON not found at {APPROVALS_PATH}")
        print("Run workflow/approval_manager.py first.")
        return 1

    approvals = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    history = (
        json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if HISTORY_PATH.exists()
        else []
    )

    status_counts = {"pending": 0, "approved": 0, "rejected": 0, "executed": 0}
    pending_savings = 0.0
    approved_savings = 0.0

    for record in approvals:
        status = str(record["status"])
        if status in status_counts:
            status_counts[status] += 1
        savings = float(record["estimated_savings"])
        if status == "pending":
            pending_savings += savings
        elif status in {"approved", "executed"}:
            approved_savings += savings

    payload = {
        "meta": {
            "generated_from": str(APPROVALS_PATH.relative_to(_PROJECT_ROOT)),
            "total": len(approvals),
        },
        "stats": {
            "total": len(approvals),
            "pending": status_counts["pending"],
            "approved": status_counts["approved"],
            "rejected": status_counts["rejected"],
            "executed": status_counts["executed"],
            "pending_savings": round(pending_savings, 2),
            "approved_savings": round(approved_savings, 2),
        },
        "approvals": approvals,
        "history": sorted(history, key=lambda e: e["timestamp"], reverse=True),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported approval data to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
