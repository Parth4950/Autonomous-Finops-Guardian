"""Export risk assessment results for the React dashboard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = _PROJECT_ROOT / "agents" / "risk_assessor" / "results" / "risk_assessment.csv"
OUTPUT_PATH = _PROJECT_ROOT / "frontend" / "src" / "data" / "risk-assessments.json"


def resource_type(resource_id: str) -> str:
    if "-healthy-" in resource_id:
        return "healthy"
    if "-zombie-" in resource_id:
        return "zombie"
    if "-seasonal-" in resource_id:
        return "seasonal"
    return "unknown"


def main() -> int:
    if not INPUT_PATH.exists():
        print(f"Risk assessment CSV not found at {INPUT_PATH}")
        print("Run agents/risk_assessor/risk_assessor.py first.")
        return 1

    df = pd.read_csv(INPUT_PATH)
    level_counts = df["risk_level"].value_counts().reindex(["low", "medium", "high"], fill_value=0)
    recommendation_counts = df["recommendation"].value_counts()

    resources = []
    for _, row in df.iterrows():
        rid = str(row["resource_id"])
        resources.append(
            {
                "resource_id": rid,
                "resource_type": resource_type(rid),
                "waste_score": round(float(row["waste_score"]), 2),
                "monthly_cost": round(float(row["monthly_cost"]), 2),
                "waste_probability": str(row["waste_probability"]),
                "environment": str(row["environment"]),
                "business_critical": bool(row["business_critical"]),
                "attached_to_load_balancer": bool(row["attached_to_load_balancer"]),
                "member_of_autoscaling_group": bool(row["member_of_autoscaling_group"]),
                "owner_exists": bool(row["owner_exists"]),
                "recent_activity_days": int(row["recent_activity_days"]),
                "risk_score": int(row["risk_score"]),
                "risk_level": str(row["risk_level"]),
                "risk_explanation": str(row["risk_explanation"]),
                "recommendation": str(row["recommendation"]),
            }
        )

    resources.sort(key=lambda r: (-r["risk_score"], -r["waste_score"]))

    high_risk = [r for r in resources if r["risk_level"] == "high"]
    scatter = [
        {
            "resource_id": r["resource_id"],
            "waste_score": r["waste_score"],
            "risk_score": r["risk_score"],
            "risk_level": r["risk_level"],
            "monthly_cost": r["monthly_cost"],
            "environment": r["environment"],
        }
        for r in resources
    ]

    payload = {
        "meta": {"generated_from": str(INPUT_PATH.relative_to(_PROJECT_ROOT)), "total": len(resources)},
        "stats": {
            "total": len(resources),
            "low": int(level_counts["low"]),
            "medium": int(level_counts["medium"]),
            "high": int(level_counts["high"]),
            "safe_to_remediate": int(recommendation_counts.get("Safe To Remediate", 0)),
            "manual_review": int(recommendation_counts.get("Manual Review Required", 0)),
            "do_not_remediate": int(recommendation_counts.get("Do Not Remediate", 0)),
            "avg_risk_score": round(float(df["risk_score"].mean()), 1),
        },
        "distribution": [
            {"level": "low", "count": int(level_counts["low"])},
            {"level": "medium", "count": int(level_counts["medium"])},
            {"level": "high", "count": int(level_counts["high"])},
        ],
        "resources": resources,
        "high_risk": high_risk,
        "scatter": scatter,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Exported risk data to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
