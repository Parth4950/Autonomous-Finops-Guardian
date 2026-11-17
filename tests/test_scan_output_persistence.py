from __future__ import annotations

import csv
import json
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.auth import User
from backend.models.finops import Anomaly, Approval, FinOpsReport, Forecast, Resource, Scan, ScanResourceSnapshot
from backend.services.scan_output_persistence import persist_scan_outputs


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_scan_workspace_outputs_are_normalized_to_owned_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'persistence-test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    workspace = tmp_path / "workspace"
    scan_id = str(uuid.uuid4())
    with factory() as db:
        user = User(full_name="Pipeline Owner", username="pipeline-owner", email="owner@example.test", password_hash="test-only")
        db.add(user)
        db.flush()
        user_id = user.id
        db.add(Scan(scan_id=scan_id, user_id=user_id, mode="synthetic", status="running", progress=100))
        db.commit()

        resource = {"resource_id": "i-synthetic-1", "avg_cpu": "12.5", "avg_network_in": "3", "avg_network_out": "4", "monthly_cost": "15.25", "resource_label": "normal"}
        _write_csv(workspace / "synthetic_data" / "cloud_resources.csv", [resource])
        (workspace / "synthetic_data").mkdir(parents=True, exist_ok=True)
        (workspace / "synthetic_data" / "scan_source.json").write_text(json.dumps({"mode": "synthetic", "resource_count": 1}), encoding="utf-8")
        _write_csv(workspace / "ml" / "isolation_forest" / "results" / "predictions.csv", [{**resource, "prediction": "1", "anomaly_score": "0.02", "prediction_label": "normal"}])
        forecast = {"resource_id": resource["resource_id"], "historical_avg_cpu": "11", "forecast_avg_cpu": "12", "forecast_min_cpu": "8", "forecast_max_cpu": "16", "utilization_category": "healthy", "waste_probability": "low"}
        _write_csv(workspace / "ml" / "forecasting" / "results" / "forecast_results.csv", [forecast])
        (workspace / "ml" / "forecasting" / "results" / "forecast_series_cache.json").write_text(json.dumps({resource["resource_id"]: {"forecast_start": "2026-01-01", "historical": [], "forecast": []}}), encoding="utf-8")
        dashboard = {"meta": {"history_days": 30, "forecast_days": 30, "generated_from": "forecast_results.csv"}, "stats": {"total": 1}, "waste_distribution": [], "resources": [forecast], "chart_data": {}}
        (workspace / "ml" / "forecasting" / "results" / "forecast_dashboard.json").write_text(json.dumps(dashboard), encoding="utf-8")
        _write_csv(workspace / "agents" / "risk_assessor" / "results" / "risk_assessment.csv", [{"resource_id": resource["resource_id"], "risk_score": "1", "risk_level": "low"}])
        _write_csv(workspace / "agents" / "auditor" / "results" / "audit_results.csv", [{"resource_id": resource["resource_id"], "monthly_cost": "15.25"}])
        _write_csv(workspace / "agents" / "planner" / "results" / "remediation_plan.csv", [{"resource_id": resource["resource_id"], "action": "stop"}])
        package = {"resource_id": resource["resource_id"], "action": "stop", "risk_level": "low", "estimated_savings": 2.0, "business_justification": "Review required", "execution_steps": ["review"]}
        (workspace / "agents" / "planner" / "results" / "approval_packages.json").write_text(json.dumps([package]), encoding="utf-8")
        (workspace / "agents" / "auditor" / "results" / "executive_report.json").write_text(json.dumps({"executive_summary": "summary"}), encoding="utf-8")

        persist_scan_outputs(db, user_id=user_id, scan_id=scan_id, workspace=workspace)
        db.commit()

        assert len(db.scalars(select(Resource).where(Resource.user_id == user_id)).all()) == 1
        assert len(db.scalars(select(ScanResourceSnapshot).where(ScanResourceSnapshot.scan_id == scan_id, ScanResourceSnapshot.user_id == user_id)).all()) == 1
        assert len(db.scalars(select(Anomaly).where(Anomaly.scan_id == scan_id, Anomaly.user_id == user_id)).all()) == 1
        assert len(db.scalars(select(Forecast).where(Forecast.scan_id == scan_id, Forecast.user_id == user_id)).all()) == 1
        assert db.scalar(select(FinOpsReport).where(FinOpsReport.scan_id == scan_id, FinOpsReport.report_type == "forecast_dashboard")).report_data == dashboard
        assert len(db.scalars(select(Approval).where(Approval.scan_id == scan_id, Approval.user_id == user_id)).all()) == 1
    Base.metadata.drop_all(engine)
    engine.dispose()
