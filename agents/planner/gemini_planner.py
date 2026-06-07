"""
Gemini-powered justification layer for the Planner Agent.

Gemini explains predetermined remediation actions — it never selects or overrides them.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv

try:
    import pip_system_certs  # noqa: F401 — use Windows certificate store for SSL
except ImportError:
    pass

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "remediation_plan.txt"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

RemediationAction = Literal[
    "terminate",
    "resize",
    "stop",
    "snapshot_and_delete",
    "manual_review",
    "ignore",
]


class GeminiConfigurationError(ValueError):
    """Raised when Gemini API configuration is invalid."""


@dataclass(frozen=True)
class PlanningContext:
    """Input context for generating remediation justifications."""

    resource_id: str
    resource_type: str
    environment: str
    business_critical: bool
    attached_to_load_balancer: bool
    member_of_autoscaling_group: bool
    owner_exists: bool
    recent_activity_days: int
    waste_score: float
    risk_score: int
    risk_level: str
    recommendation: str
    risk_explanation: str
    monthly_cost: float
    annual_cost: float
    potential_annual_savings: float
    action: RemediationAction
    execution_steps: list[str]


@dataclass(frozen=True)
class PlanningJustification:
    """Structured justification output from Gemini or fallback templates."""

    business_justification: str
    technical_justification: str
    expected_outcome: str
    estimated_savings: float
    source: Literal["gemini", "fallback"]


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


class GeminiPlanner:
    """
    Generate business and technical justifications using the Gemini API.

    Remediation actions are supplied as fixed inputs. Gemini is constrained
    to justify — never to determine — the selected action.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
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
            logger.warning(
                "GEMINI_API_KEY not set — using deterministic fallback justifications."
            )

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
            logger.info("Gemini planner initialized with model: %s", self._model_name)
        except ImportError as exc:
            raise GeminiConfigurationError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

    def generate_justification(self, context: PlanningContext) -> PlanningJustification:
        """
        Generate remediation justifications for a single resource.

        Args:
            context: Predetermined action, risk, and financial context.

        Returns:
            PlanningJustification with business/technical narratives.
        """
        if not self._client:
            return self._fallback_justification(context)

        try:
            prompt = self._build_prompt(context)
            response_text = self._call_gemini(prompt)
            parsed = self._parse_json_response(response_text)
            return PlanningJustification(
                business_justification=str(parsed.get("business_justification", "")).strip(),
                technical_justification=str(parsed.get("technical_justification", "")).strip(),
                expected_outcome=str(parsed.get("expected_outcome", "")).strip(),
                estimated_savings=self._validate_savings(
                    parsed.get("estimated_savings"),
                    context.potential_annual_savings,
                    context.action,
                ),
                source="gemini",
            )
        except Exception as exc:
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                logger.error(
                    "Gemini quota exhausted — using fallback justifications."
                )
            else:
                logger.warning(
                    "Gemini planning failed for %s: %s — using fallback.",
                    context.resource_id,
                    exc,
                )
            return self._fallback_justification(context)

    def generate_batch(
        self,
        contexts: list[PlanningContext],
    ) -> list[PlanningJustification]:
        """Generate justifications for multiple resources."""
        results: list[PlanningJustification] = []

        for index, context in enumerate(contexts, start=1):
            results.append(self.generate_justification(context))
            if index % 20 == 0:
                logger.info("Gemini planning progress: %d / %d", index, len(contexts))

        return results

    def _build_prompt(self, context: PlanningContext) -> str:
        steps_text = "\n".join(
            f"{step_number}. {step}"
            for step_number, step in enumerate(context.execution_steps, start=1)
        )
        return self._prompt_template.format(
            resource_id=context.resource_id,
            resource_type=context.resource_type,
            environment=context.environment,
            business_critical=context.business_critical,
            attached_to_load_balancer=context.attached_to_load_balancer,
            member_of_autoscaling_group=context.member_of_autoscaling_group,
            owner_exists=context.owner_exists,
            recent_activity_days=context.recent_activity_days,
            waste_score=context.waste_score,
            risk_score=context.risk_score,
            risk_level=context.risk_level,
            recommendation=context.recommendation,
            risk_explanation=context.risk_explanation,
            monthly_cost=context.monthly_cost,
            annual_cost=context.annual_cost,
            potential_annual_savings=context.potential_annual_savings,
            action=context.action,
            execution_steps=steps_text,
        )

    def _call_gemini(self, prompt: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise ValueError("Gemini returned an empty planning response.")
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
    def _validate_savings(
        gemini_savings: Any,
        predetermined: float,
        action: RemediationAction,
    ) -> float:
        """Ensure savings align with predetermined financial analysis."""
        if action in ("ignore", "manual_review"):
            return 0.0 if action == "ignore" else round(predetermined * 0.5, 2)

        try:
            parsed = float(gemini_savings)
        except (TypeError, ValueError):
            return round(predetermined, 2)

        if abs(parsed - predetermined) > max(1.0, predetermined * 0.05):
            logger.debug(
                "Gemini savings $%.2f overridden to predetermined $%.2f",
                parsed,
                predetermined,
            )
        return round(predetermined, 2)

    @staticmethod
    def _fallback_justification(context: PlanningContext) -> PlanningJustification:
        """Generate template-based justifications when Gemini is unavailable."""
        savings = (
            0.0
            if context.action == "ignore"
            else round(context.potential_annual_savings * 0.5, 2)
            if context.action == "manual_review"
            else round(context.potential_annual_savings, 2)
        )

        action_labels = {
            "terminate": "terminating this instance",
            "resize": "rightsizing this instance",
            "stop": "stopping this instance",
            "snapshot_and_delete": "snapshotting and deleting this EBS volume",
            "manual_review": "flagging this resource for manual review",
            "ignore": "deferring remediation on this resource",
        }
        action_label = action_labels.get(context.action, context.action)

        business = (
            f"{action_label.capitalize()} is expected to recover approximately "
            f"${savings:,.2f} annually. Risk analysis indicates {context.risk_level} "
            f"operational risk ({context.recommendation}), with a waste score of "
            f"{context.waste_score:.1f}."
        )

        technical = (
            f"The predetermined action '{context.action}' follows the Planner rules "
            f"engine based on resource type '{context.resource_type}', risk level "
            f"'{context.risk_level}', and waste score {context.waste_score:.1f}. "
            f"Execution will follow the defined step sequence with verification gates."
        )

        if context.action == "ignore":
            outcome = (
                "No changes will be made; the resource remains under monitoring "
                "due to high operational risk or insufficient waste signal."
            )
        elif context.action == "manual_review":
            outcome = (
                "Resource will be queued for stakeholder review before any "
                "infrastructure changes are executed."
            )
        else:
            outcome = (
                f"Successful execution is expected to eliminate idle spend and "
                f"recover up to ${savings:,.2f} in annual cloud costs."
            )

        return PlanningJustification(
            business_justification=business,
            technical_justification=technical,
            expected_outcome=outcome,
            estimated_savings=savings,
            source="fallback",
        )
