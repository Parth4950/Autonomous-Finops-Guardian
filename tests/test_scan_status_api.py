"""Scan status API preserves per-stage failures for the frontend."""

from types import SimpleNamespace

from backend.api.scan import get_scan_status
from backend.schemas.scan import ScanStartRequest
from backend.services.scan_service import build_pipeline_steps


def test_scan_start_requires_an_explicit_mode_and_keeps_all_eight_stages() -> None:
    assert ScanStartRequest.model_fields["mode"].is_required()

    for mode, discovery_script in (
        ("synthetic", "synthetic_data/generate_resources.py"),
        ("aws", "agents/scout/export_resources.py"),
    ):
        stages = build_pipeline_steps(mode)
        assert len(stages) == 8
        assert stages[0][1] == discovery_script


def test_scan_status_includes_stage_error_detail() -> None:
    state = SimpleNamespace(
        scan_id="scan-1",
        status="failed",
        progress=12,
        scan_mode="aws",
        current_step="Discovering AWS resources",
        steps=[
            {
                "name": "Discovering AWS resources",
                "status": "failed",
                "error": "AWS API denied ec2:DescribeInstances",
            }
        ],
        message="Scan failed",
        error="Discovering AWS resources failed: AWS API denied ec2:DescribeInstances",
    )
    service = SimpleNamespace(get_status=lambda user_id: state)

    response = get_scan_status(service=service, user=SimpleNamespace(id=42))

    assert response.steps[0].status == "failed"
    assert response.steps[0].error == "AWS API denied ec2:DescribeInstances"
