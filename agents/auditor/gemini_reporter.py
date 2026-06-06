"""
Gemini-powered executive report generator for the Auditor Agent.

Synthesizes predetermined financial metrics into executive-level narratives.
Gemini does not calculate savings — it only reports pre-computed figures.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from dotenv import load_dotenv

try:
    import pip_system_certs  # noqa: F401 — use Windows certificate store for SSL
except ImportError:
    pass

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "executive_report.txt"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class AuditAggregateMetrics:
    """Predetermined aggregate financial metrics for executive reporting."""

    total_resources: int
    total_monthly_cost: float
    total_annual_cost: float
    potential_monthly_savings: float
    potential_annual_savings: float
    safe_count: int
    manual_count: int
    do_not_count: int
    critical_count: int
    high_count: int
    top_opportunities_text: str


@dataclass(frozen=True)
class ExecutiveReport:
    """Structured executive FinOps report."""

    executive_summary: str
    key_findings: list[str]
    top_cost_drivers: list[str]
    recommended_actions: list[str]
    risk_considerations: list[str]
    estimated_savings: dict[str, float]
    source: Literal["gemini", "fallback"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "executive_summary": self.executive_summary,
            "key_findings": self.key_findings,
            "top_cost_drivers": self.top_cost_drivers,
            "recommended_actions": self.recommended_actions,
            "risk_considerations": self.risk_considerations,
            "estimated_savings": self.estimated_savings,
            "source": self.source,
        }


def _configure_ssl_certificates() -> None:
    """Point HTTP/gRPC clients at a trusted CA bundle (fixes Windows SSL errors)."""
    try:
        import certifi

        bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle)
        os.environ.setdefault("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH", bundle)
    except ImportError:
        pass


class GeminiReporter:
    """
    Generate executive FinOps reports using the Gemini API.

    All financial figures are supplied as fixed inputs. Gemini synthesizes
    narrative — it never recalculates savings or costs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.0-flash",
        prompt_path: Path = _PROMPT_PATH,
    ) -> None:
        load_dotenv(_ENV_FILE, override=True)
        _configure_ssl_certificates()

        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self._model_name = model_name
        self._prompt_template = self._load_prompt_template(prompt_path)
        self._client: Any | None = None

        if self._api_key:
            self._initialize_client()
        else:
            logger.warning("GEMINI_API_KEY not set — using fallback executive report.")

    @property
    def is_gemini_available(self) -> bool:
        """Return True when Gemini client is configured."""
        return bool(self._api_key and self._client)

    def _load_prompt_template(self, prompt_path: Path) -> str:
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def _initialize_client(self) -> None:
        try:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
            logger.info("Gemini reporter initialized with model: %s", self._model_name)
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

    @staticmethod
    def build_aggregate_metrics(
        audit_results: pd.DataFrame,
        top_n: int = 10,
    ) -> AuditAggregateMetrics:
        """Compute aggregate metrics from audit results for reporting."""
        top = audit_results.nlargest(top_n, "potential_monthly_savings")
        lines = [
            (
                f"- {row['resource_id']}: ${row['monthly_cost']:.2f}/mo, "
                f"waste={row['waste_score']:.1f}, "
                f"savings=${row['potential_monthly_savings']:.2f}/mo, "
                f"{row['recommendation']}"
            )
            for _, row in top.iterrows()
        ]

        return AuditAggregateMetrics(
            total_resources=len(audit_results),
            total_monthly_cost=float(audit_results["monthly_cost"].sum()),
            total_annual_cost=float(audit_results["annual_cost"].sum()),
            potential_monthly_savings=float(audit_results["potential_monthly_savings"].sum()),
            potential_annual_savings=float(audit_results["potential_annual_savings"].sum()),
            safe_count=int((audit_results["recommendation"] == "Safe To Remediate").sum()),
            manual_count=int(
                (audit_results["recommendation"] == "Manual Review Required").sum()
            ),
            do_not_count=int((audit_results["recommendation"] == "Do Not Remediate").sum()),
            critical_count=int(
                (audit_results["priority_category"] == "Critical Savings Opportunity").sum()
            ),
            high_count=int(
                (audit_results["priority_category"] == "High Savings Opportunity").sum()
            ),
            top_opportunities_text="\n".join(lines) if lines else "No opportunities found.",
        )

    def generate_report(
        self,
        audit_results: pd.DataFrame,
    ) -> ExecutiveReport:
        """
        Generate an executive FinOps report from audit results.

        Args:
            audit_results: Full audit DataFrame with cost and savings columns.

        Returns:
            ExecutiveReport with summary, findings, and recommendations.
        """
        metrics = self.build_aggregate_metrics(audit_results)

        if not self._client:
            return self._fallback_report(metrics)

        try:
            prompt = self._prompt_template.format(
                total_resources=metrics.total_resources,
                total_monthly_cost=metrics.total_monthly_cost,
                total_annual_cost=metrics.total_annual_cost,
                potential_monthly_savings=metrics.potential_monthly_savings,
                potential_annual_savings=metrics.potential_annual_savings,
                safe_count=metrics.safe_count,
                manual_count=metrics.manual_count,
                do_not_count=metrics.do_not_count,
                critical_count=metrics.critical_count,
                high_count=metrics.high_count,
                top_opportunities=metrics.top_opportunities_text,
            )
            response_text = self._call_gemini(prompt)
            parsed = self._parse_json_response(response_text)
            return ExecutiveReport(
                executive_summary=str(parsed.get("executive_summary", "")).strip(),
                key_findings=list(parsed.get("key_findings", [])),
                top_cost_drivers=list(parsed.get("top_cost_drivers", [])),
                recommended_actions=list(parsed.get("recommended_actions", [])),
                risk_considerations=list(parsed.get("risk_considerations", [])),
                estimated_savings=dict(parsed.get("estimated_savings", {})),
                source="gemini",
            )
        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                logger.error(
                    "Gemini quota exhausted — using fallback executive report."
                )
            else:
                logger.warning("Gemini report failed: %s — using fallback.", exc)
            return self._fallback_report(metrics)

    def _call_gemini(self, prompt: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise ValueError("Gemini returned an empty executive report.")
        return response.text

    @staticmethod
    def _parse_json_response(response_text: str) -> dict[str, Any]:
        cleaned = response_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if brace_match:
                return json.loads(brace_match.group(0))
            raise

    @staticmethod
    def _fallback_report(metrics: AuditAggregateMetrics) -> ExecutiveReport:
        """Generate a deterministic executive report when Gemini is unavailable."""
        summary = (
            f"We identified {metrics.total_resources} cloud resources representing "
            f"${metrics.total_monthly_cost:,.2f} in monthly spend and "
            f"${metrics.total_annual_cost:,.2f} annually. "
            f"Potential recoverable savings are ${metrics.potential_monthly_savings:,.2f}/month "
            f"(${metrics.potential_annual_savings:,.2f}/year). "
            f"{metrics.safe_count} resources are classified as low-risk remediation candidates."
        )

        return ExecutiveReport(
            executive_summary=summary,
            key_findings=[
                f"{metrics.critical_count + metrics.high_count} resources flagged as critical or high savings opportunities.",
                f"{metrics.safe_count} resources are safe to remediate immediately.",
                f"${metrics.potential_monthly_savings:,.2f}/month in savings requires only low-risk actions.",
            ],
            top_cost_drivers=[
                "Underutilized compute resources with high waste scores.",
                "Zombie instances incurring cost without productive utilization.",
                "Resources with safe remediation status driving immediate savings potential.",
            ],
            recommended_actions=[
                f"Prioritize remediation of {metrics.safe_count} safe-to-remediate resources.",
                f"Schedule manual review for {metrics.manual_count} medium-risk resources.",
                f"Defer action on {metrics.do_not_count} high-risk production resources.",
            ],
            risk_considerations=[
                f"{metrics.do_not_count} resources require do-not-remediate status due to operational risk.",
                f"{metrics.manual_count} resources need stakeholder approval before changes.",
                "Savings estimates assume successful rightsizing or termination of idle resources.",
            ],
            estimated_savings={
                "monthly_usd": round(metrics.potential_monthly_savings, 2),
                "annual_usd": round(metrics.potential_annual_savings, 2),
            },
            source="fallback",
        )
