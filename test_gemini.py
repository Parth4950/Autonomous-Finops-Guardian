"""Quick Gemini API connectivity test for Autonomous FinOps Guardian."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import pip_system_certs  # noqa: F401
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


def mask_key(key: str) -> str:
    if len(key) <= 10:
        return "(too short)"
    return f"{key[:6]}...{key[-4:]}"


def run_test(name: str, fn) -> bool:
    try:
        result = fn()
        print(f"  PASS — {name}")
        if result:
            print(f"         {result[:200]}")
        return True
    except Exception as exc:
        print(f"  FAIL — {name}")
        print(f"         {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    key = os.getenv("GEMINI_API_KEY", "").strip()

    print("\n=== GEMINI API KEY CHECK ===\n")
    print(f"Key present : {bool(key)}")
    print(f"Key length  : {len(key)}")
    print(f"Key masked  : {mask_key(key)}")

    if not key:
        print("\nFAIL: GEMINI_API_KEY is not set in .env")
        return 1

    if not key.startswith("AIza"):
        print(
            "WARN: Key does not start with 'AIza'. "
            "Google AI Studio keys usually look like AIzaSy..."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    print("Client init : OK\n")

    results: list[bool] = []

    print("Model availability:")
    model_candidates = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]
    for model_name in model_candidates:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Reply with exactly: OK",
                config=types.GenerateContentConfig(temperature=0.0),
            )
            text = (response.text or "").strip()
            print(f"  {model_name}: PASS ({text[:40]})")
        except Exception as exc:
            err = str(exc)
            if "401" in err or "403" in err or "invalid" in err.lower() and "credential" in err.lower():
                label = "AUTH FAIL"
            elif "404" in err or "not found" in err.lower():
                label = "NOT FOUND"
            elif "429" in err or "RESOURCE_EXHAUSTED" in err:
                label = "QUOTA EXHAUSTED (429)"
            else:
                label = f"FAIL ({type(exc).__name__})"
            print(f"  {model_name}: {label}")

    print()

    def simple_ping() -> str:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Reply with exactly: GEMINI_OK",
            config=types.GenerateContentConfig(temperature=0.0),
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Empty response")
        return text

    def json_mode() -> str:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents='Return JSON only: {"status": "ok", "agent": "finops"}',
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        text = (response.text or "").strip()
        parsed = json.loads(text)
        if parsed.get("status") != "ok":
            raise ValueError(f"Unexpected JSON: {parsed}")
        return text

    print("Direct API tests:")
    results.append(run_test("Simple text generation", simple_ping))
    results.append(run_test("JSON mode (agent format)", json_mode))

    print("\nAgent integration tests:")

    from agents.risk_assessor.gemini_explainer import (
        GeminiExplainer,
        RiskExplanationContext,
    )
    from agents.auditor.gemini_reporter import GeminiReporter
    from agents.planner.gemini_planner import GeminiPlanner, PlanningContext

    explainer = GeminiExplainer()
    print(f"  Risk Assessor — Gemini available: {explainer.is_gemini_available}")

    context = RiskExplanationContext(
        resource_id="res-test-001",
        environment="development",
        business_critical=False,
        attached_to_load_balancer=False,
        member_of_autoscaling_group=False,
        owner_exists=True,
        recent_activity_days=90,
        waste_score=95.0,
        monthly_cost=50.0,
        waste_probability="high",
        risk_score=5,
        risk_level="low",
    )

    def risk_explainer() -> str:
        result = explainer.explain(context)
        if result.source != "gemini":
            raise ValueError(f"Used fallback instead of Gemini (source={result.source})")
        return result.risk_explanation[:120]

    results.append(run_test("Risk Assessor (GeminiExplainer)", risk_explainer))

    reporter = GeminiReporter()
    print(f"  Auditor       — Gemini available: {reporter.is_gemini_available}")

    import pandas as pd

    sample_audit = pd.DataFrame(
        [
            {
                "resource_id": "res-zombie-001",
                "monthly_cost": 100.0,
                "annual_cost": 1200.0,
                "waste_score": 97.0,
                "potential_monthly_savings": 100.0,
                "potential_annual_savings": 1200.0,
                "recommendation": "Safe To Remediate",
                "priority_category": "High Savings Opportunity",
            }
        ]
    )

    def auditor_report() -> str:
        report = reporter.generate_report(sample_audit)
        if report.source != "gemini":
            raise ValueError(f"Used fallback instead of Gemini (source={report.source})")
        return report.executive_summary[:120]

    results.append(run_test("Auditor (GeminiReporter)", auditor_report))

    planner = GeminiPlanner()
    print(f"  Planner       — Gemini available: {planner.is_gemini_available}")

    plan_context = PlanningContext(
        resource_id="res-zombie-001",
        resource_type="zombie",
        environment="development",
        business_critical=False,
        attached_to_load_balancer=False,
        member_of_autoscaling_group=False,
        owner_exists=True,
        recent_activity_days=90,
        waste_score=97.0,
        risk_score=5,
        risk_level="low",
        recommendation="Safe To Remediate",
        risk_explanation="Test resource with high waste and low risk.",
        monthly_cost=100.0,
        annual_cost=1200.0,
        potential_annual_savings=1200.0,
        action="terminate",
        execution_steps=["Create backup", "Verify backup", "Terminate instance"],
    )

    def planner_justification() -> str:
        result = planner.generate_justification(plan_context)
        if result.source != "gemini":
            raise ValueError(f"Used fallback instead of Gemini (source={result.source})")
        return result.business_justification[:120]

    results.append(run_test("Planner (GeminiPlanner)", planner_justification))

    passed = sum(results)
    total = len(results)
    print(f"\n=== RESULT: {passed}/{total} tests passed ===\n")

    if passed == total:
        print("Gemini is responding properly across all agents.")
        return 0

    print("Some tests failed — see errors above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
