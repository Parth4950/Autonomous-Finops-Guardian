"""
Autonomous FinOps Guardian — FastAPI backend.

Exposes agent pipeline outputs and governance workflows via REST APIs.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure project root is importable for agent and workflow packages.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.api import anomalies, approvals, audit, execution, forecast, health, planner, resources, risk, scan, waste
from backend.services.data_loader import DataNotFoundError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Autonomous FinOps Guardian API starting")
    yield
    logger.info("Autonomous FinOps Guardian API shutting down")


app = FastAPI(
    title="Autonomous FinOps Guardian API",
    description=(
        "Enterprise REST API for cloud cost optimization, risk assessment, "
        "remediation planning, human approval governance, and execution tracking."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(scan.router)
app.include_router(resources.router)
app.include_router(waste.router)
app.include_router(anomalies.router)
app.include_router(forecast.router)
app.include_router(risk.router)
app.include_router(audit.router)
app.include_router(planner.router)
app.include_router(approvals.router)
app.include_router(execution.router)


@app.exception_handler(DataNotFoundError)
async def data_not_found_handler(_: Request, exc: DataNotFoundError) -> JSONResponse:
    """Map missing agent output files to HTTP 404."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    """Root redirect metadata."""
    return {
        "service": "Autonomous FinOps Guardian API",
        "docs": "/docs",
        "health": "/health",
    }
