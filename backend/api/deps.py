"""FastAPI dependency injection providers."""

from __future__ import annotations

from functools import lru_cache

from backend.services.anomaly_service import AnomalyService
from backend.services.approval_service import ApprovalService
from backend.services.audit_service import AuditService
from backend.services.execution_service import ExecutionService
from backend.services.forecast_service import ForecastService
from backend.services.planner_service import PlannerService
from backend.services.resource_service import ResourceService
from backend.services.risk_service import RiskService
from backend.services.scan_service import ScanService
from backend.services.waste_service import WasteService


@lru_cache
def get_resource_service() -> ResourceService:
    return ResourceService()


@lru_cache
def get_waste_service() -> WasteService:
    return WasteService()


@lru_cache
def get_anomaly_service() -> AnomalyService:
    return AnomalyService()


@lru_cache
def get_forecast_service() -> ForecastService:
    return ForecastService()


@lru_cache
def get_risk_service() -> RiskService:
    return RiskService()


@lru_cache
def get_audit_service() -> AuditService:
    return AuditService()


@lru_cache
def get_planner_service() -> PlannerService:
    return PlannerService()


@lru_cache
def get_approval_service() -> ApprovalService:
    return ApprovalService()


@lru_cache
def get_execution_service() -> ExecutionService:
    return ExecutionService()


@lru_cache
def get_scan_service() -> ScanService:
    return ScanService()
