from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.security import token_hash
from backend.config import cors_allow_origins
from backend.db.session import get_db
from backend.models.auth import User, UserSession
from backend.models.finops import FinOpsReport, Scan, ScanResourceSnapshot
from backend.models.paths import PROJECT_ROOT
from backend.services.scan_output_persistence import persist_scan_outputs

SESSION_COOKIE = "finops_session"
CSRF_COOKIE = "finops_csrf"
SIMULATION_HEADER = "x-finops-mode"
SIMULATION_USERNAME = "__simulation_demo__"
SIMULATION_EMAIL = "simulation@finops.local"
SIMULATION_SEED_SCAN_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "finops-simulation-seed-scan"))


def is_simulation_user(user: User) -> bool:
    """Return True when the resolved actor is the isolated simulation demo workspace."""
    return user.username == SIMULATION_USERNAME


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    origin = request.headers.get("origin", "")
    if not origin or origin not in cors_allow_origins() or not cookie or not header or cookie != header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def _get_or_seed_simulation_user(db: Session) -> User:
    """Return the dedicated non-login simulation user, seeding demo artifacts once if needed."""
    sim_user = db.scalar(select(User).where(User.username == SIMULATION_USERNAME))
    created_or_seeded = False
    if sim_user is None:
        sim_user = User(
            full_name="Simulation Mode Demo",
            username=SIMULATION_USERNAME,
            email=SIMULATION_EMAIL,
            password_hash="!simulation-disabled!",
            is_active=False,
        )
        db.add(sim_user)
        db.flush()
        created_or_seeded = True

    latest_completed_scan = db.scalar(
        select(Scan)
        .where(Scan.user_id == sim_user.id, Scan.status == "completed")
        .order_by(Scan.created_at.desc())
        .limit(1)
    )
    ready_report_types = {
        "risk_assessments",
        "audit_results",
        "executive_report",
        "forecast_dashboard",
        "forecast_results",
        "anomalies",
        "plans",
        "scan_source",
    }
    if latest_completed_scan is not None:
        snapshot_count = db.scalar(
            select(ScanResourceSnapshot.snapshot_id)
            .where(
                ScanResourceSnapshot.user_id == sim_user.id,
                ScanResourceSnapshot.scan_id == latest_completed_scan.scan_id,
            )
            .limit(1)
        )
        report_types = set(db.scalars(
            select(FinOpsReport.report_type).where(
                FinOpsReport.user_id == sim_user.id,
                FinOpsReport.scan_id == latest_completed_scan.scan_id,
            )
        ).all())
        simulation_data_ready = snapshot_count is not None and ready_report_types.issubset(report_types)
    else:
        simulation_data_ready = False

    if not simulation_data_ready and (PROJECT_ROOT / "synthetic_data" / "cloud_resources.csv").is_file():
        now = datetime.now(timezone.utc)
        # Keep older incomplete scan records intact; write a fresh, complete scan instead.
        existing_seed = db.get(Scan, SIMULATION_SEED_SCAN_ID)
        scan_id = SIMULATION_SEED_SCAN_ID if existing_seed is None else str(uuid.uuid4())
        seed_scan = Scan(
            scan_id=scan_id,
            user_id=sim_user.id,
            mode="synthetic",
            status="completed",
            progress=100,
            current_stage="Remediation Planner",
            message="Simulation demo scan ready",
            started_at=now,
            completed_at=now,
        )
        db.add(seed_scan)
        db.flush()
        persist_scan_outputs(
            db,
            user_id=sim_user.id,
            scan_id=seed_scan.scan_id,
            workspace=PROJECT_ROOT,
        )
        created_or_seeded = True

    if created_or_seeded:
        db.commit()
        db.refresh(sim_user)
    return sim_user


def current_user(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    row = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(session_token)))
    now = datetime.now(timezone.utc)
    if row is None or row.revoked_at is not None or row.expires_at.replace(tzinfo=timezone.utc) <= now or not row.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
        csrf_header = request.headers.get("x-csrf-token", "")
        origin = request.headers.get("origin", "")
        if not origin or origin not in cors_allow_origins() or not csrf_cookie or not csrf_header or csrf_cookie != csrf_header or token_hash(csrf_cookie) != row.csrf_token_hash:
            raise HTTPException(status_code=403, detail="CSRF validation failed")
    return row.user


def current_user_or_simulation(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    """Resolve either the isolated simulation workspace (when X-FinOps-Mode: simulation) or an authenticated user."""
    mode_header = request.headers.get(SIMULATION_HEADER, "").strip().lower()
    if mode_header == "simulation":
        require_csrf(request)
        return _get_or_seed_simulation_user(db)
    return current_user(request=request, session_token=session_token, db=db)
