"""
Gemini-powered explanation layer for Risk Assessor.

Gemini explains predetermined risk scores — it never calculates or overrides them.
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

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "risk_explanation.txt"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"

Recommendation = Literal["Safe To Remediate", "Manual Review Required", "Do Not Remediate"]

DETERMINISTIC_RECOMMENDATIONS: dict[str, Recommendation] = {
    "low": "Safe To Remediate",
    "medium": "Manual Review Required",
    "high": "Do Not Remediate",
}


class GeminiConfigurationError(ValueError):
    """Raised when Gemini API configuration is invalid."""


@dataclass(frozen=True)
class RiskExplanationContext:
    """Input context for generating a human-readable risk explanation."""

    resource_id: str
    environment: str
    business_critical: bool
    attached_to_load_balancer: bool
    member_of_autoscaling_group: bool
    owner_exists: bool
    recent_activity_days: int
    waste_score: float
    monthly_cost: float
    waste_probability: str
    risk_score: int
    risk_level: str


@dataclass(frozen=True)
class ExplanationResult:
    """Structured explanation output from Gemini or fallback templates."""

    risk_explanation: str
    recommendation: Recommendation
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
        logger.debug("certifi not installed — skipping explicit SSL bundle configuration.")


class GeminiExplainer:
    """
    Generate human-readable risk explanations using the Gemini API.

    Risk scores and levels are supplied as fixed inputs. Gemini is constrained
    to explain — never to determine — operational risk.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
        prompt_path: Path = _PROMPT_PATH,
    ) -> None:
        """
        Initialize the explainer.

        Args:
            api_key: Optional Gemini API key. Loaded from GEMINI_API_KEY env var
                when not provided.
            model_name: Gemini model identifier.
            prompt_path: Path to the prompt template file.
        """
        load_dotenv(_ENV_FILE, override=True)
        _configure_ssl_certificates()

        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self._model_name = model_name
        self._prompt_template = self._load_prompt_template(prompt_path)
        self._client: Any | None = None

        if self._api_key:
            self._initialize_gemini_client()
        else:
            logger.warning(
                "GEMINI_API_KEY not set — using deterministic fallback explanations."
            )

    @property
    def is_gemini_available(self) -> bool:
        """Return True when a Gemini API key is configured."""
        return bool(self._api_key and self._client)

    def _load_prompt_template(self, prompt_path: Path) -> str:
        """Load the prompt template from disk."""
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def _initialize_gemini_client(self) -> None:
        """Configure the google-genai client (replaces deprecated google-generativeai)."""
        try:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
            logger.info("Gemini client initialized with model: %s", self._model_name)
        except ImportError as exc:
            raise GeminiConfigurationError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc
        except Exception as exc:
            raise GeminiConfigurationError(f"Failed to initialize Gemini client: {exc}") from exc

    def explain(self, context: RiskExplanationContext) -> ExplanationResult:
        """
        Generate a risk explanation for a single resource.

        Args:
            context: Predetermined risk and infrastructure metadata.

        Returns:
            ExplanationResult with explanation text and recommendation.
        """
        deterministic_recommendation = DETERMINISTIC_RECOMMENDATIONS.get(
            context.risk_level,
            "Manual Review Required",
        )

        if not self._client:
            return self._fallback_explanation(context, deterministic_recommendation)

        try:
            prompt = self._build_prompt(context)
            response_text = self._call_gemini(prompt)
            parsed = self._parse_json_response(response_text)
            recommendation = self._validate_recommendation(
                parsed.get("recommendation", ""),
                context.risk_level,
                deterministic_recommendation,
            )
            explanation = str(parsed.get("risk_explanation", "")).strip()
            if not explanation:
                raise ValueError("Empty risk_explanation in Gemini response.")

            return ExplanationResult(
                risk_explanation=explanation,
                recommendation=recommendation,
                source="gemini",
            )
        except Exception as exc:
            error_text = str(exc)
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                logger.error(
                    "Gemini quota/billing exhausted — add credits at "
                    "https://aistudio.google.com/ or explanations will use fallback."
                )
            else:
                logger.warning(
                    "Gemini explanation failed for %s: %s — using fallback.",
                    context.resource_id,
                    exc,
                )
            return self._fallback_explanation(context, deterministic_recommendation)

    def _call_gemini(self, prompt: str) -> str:
        """Invoke Gemini via the google-genai SDK and return response text."""
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
            raise ValueError("Gemini returned an empty response.")

        return response.text

    def explain_batch(
        self,
        contexts: list[RiskExplanationContext],
    ) -> list[ExplanationResult]:
        """
        Generate explanations for multiple resources.

        Args:
            contexts: List of explanation contexts.

        Returns:
            List of ExplanationResult objects in the same order.
        """
        results: list[ExplanationResult] = []

        for index, context in enumerate(contexts, start=1):
            results.append(self.explain(context))
            if index % 20 == 0:
                logger.info("Gemini explanation progress: %d / %d", index, len(contexts))

        return results

    def _build_prompt(self, context: RiskExplanationContext) -> str:
        """Format the prompt template with resource context."""
        return self._prompt_template.format(
            resource_id=context.resource_id,
            environment=context.environment,
            business_critical=context.business_critical,
            attached_to_load_balancer=context.attached_to_load_balancer,
            member_of_autoscaling_group=context.member_of_autoscaling_group,
            owner_exists=context.owner_exists,
            recent_activity_days=context.recent_activity_days,
            waste_score=context.waste_score,
            monthly_cost=context.monthly_cost,
            waste_probability=context.waste_probability,
            risk_score=context.risk_score,
            risk_level=context.risk_level,
        )

    @staticmethod
    def _parse_json_response(response_text: str) -> dict[str, Any]:
        """Extract and parse JSON from a Gemini response."""
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
    def _validate_recommendation(
        gemini_recommendation: str,
        risk_level: str,
        deterministic: Recommendation,
    ) -> Recommendation:
        """
        Ensure the recommendation aligns with the predetermined risk level.

        Gemini may phrase the recommendation, but the rules engine has final say.
        """
        normalized = gemini_recommendation.strip().lower()
        expected = deterministic.lower()

        if expected in normalized or normalized in expected:
            return deterministic

        logger.debug(
            "Gemini recommendation '%s' overridden to deterministic '%s' for risk_level=%s",
            gemini_recommendation,
            deterministic,
            risk_level,
        )
        return deterministic

    @staticmethod
    def _fallback_explanation(
        context: RiskExplanationContext,
        recommendation: Recommendation,
    ) -> ExplanationResult:
        """Generate a template-based explanation when Gemini is unavailable."""
        risk_factors: list[str] = []

        if context.environment == "production":
            risk_factors.append("production environment")
        if context.business_critical:
            risk_factors.append("business-critical designation")
        if context.member_of_autoscaling_group:
            risk_factors.append("Auto Scaling Group membership")
        if context.attached_to_load_balancer:
            risk_factors.append("load balancer attachment")
        if context.recent_activity_days < 30:
            risk_factors.append(f"recent activity ({context.recent_activity_days} days ago)")
        if context.owner_exists:
            risk_factors.append("identified resource owner")

        if risk_factors:
            factor_text = ", ".join(risk_factors)
            explanation = (
                f"Resource {context.resource_id} has a predetermined risk score of "
                f"{context.risk_score} ({context.risk_level} risk) due to: {factor_text}. "
                f"Although the waste score is {context.waste_score} with {context.waste_probability} "
                f"waste probability, infrastructure dependencies may affect remediation safety."
            )
        else:
            explanation = (
                f"Resource {context.resource_id} has a predetermined risk score of "
                f"{context.risk_score} ({context.risk_level} risk). "
                f"Waste score is {context.waste_score} with {context.waste_probability} "
                f"waste probability and limited operational dependencies detected."
            )

        return ExplanationResult(
            risk_explanation=explanation,
            recommendation=recommendation,
            source="fallback",
        )
