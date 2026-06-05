"""
Scout Agent — orchestrates AWS resource discovery.

Runs EC2 and EBS scanners and returns a unified list of findings.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# Allow `python agents/scout/scout_agent.py` from any working directory.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.scout.ebs_scanner import EBSScanner
from agents.scout.ec2_scanner import EC2Scanner
from backend.utils.aws_client import AWSClientError, AWSClientHelper, AWSConfigurationError

logger = logging.getLogger(__name__)


class ScoutAgent:
    """
    Orchestrate EC2 and EBS resource discovery.

    Executes individual scanners, merges their findings into a single
    unified list suitable for downstream ML and risk analysis agents.
    """

    def __init__(
        self,
        aws_client: AWSClientHelper | None = None,
        ec2_scanner: EC2Scanner | None = None,
        ebs_scanner: EBSScanner | None = None,
    ) -> None:
        """
        Initialize the scout agent and its scanners.

        Args:
            aws_client: Shared AWS client helper passed to scanners.
            ec2_scanner: Optional pre-configured EC2 scanner instance.
            ebs_scanner: Optional pre-configured EBS scanner instance.
        """
        self._aws_client = aws_client or AWSClientHelper()
        self._ec2_scanner = ec2_scanner or EC2Scanner(aws_client=self._aws_client)
        self._ebs_scanner = ebs_scanner or EBSScanner(aws_client=self._aws_client)

    @property
    def region(self) -> str:
        """Return the AWS region being scanned."""
        return self._aws_client.region

    def run(self) -> list[dict[str, Any]]:
        """
        Execute all scanners and return merged findings.

        Returns:
            Unified list of EC2 and EBS resource dictionaries.

        Raises:
            AWSClientError: If any scanner API call fails.
        """
        logger.info("Scout agent starting discovery in region: %s", self.region)

        ec2_findings = self._ec2_scanner.scan()
        ebs_findings = self._ebs_scanner.scan()
        findings = ec2_findings + ebs_findings

        logger.info(
            "Scout agent complete — %d EC2, %d EBS, %d total",
            len(ec2_findings),
            len(ebs_findings),
            len(findings),
        )
        return findings


def format_findings(findings: list[dict[str, Any]]) -> str:
    """
    Format scout findings for human-readable console output.

    Args:
        findings: Unified list of resource dictionaries from ScoutAgent.run().

    Returns:
        A formatted multi-line string.
    """
    if not findings:
        return "No resources found."

    lines: list[str] = []

    for index, finding in enumerate(findings, start=1):
        resource_type = finding.get("resource_type", "unknown").upper()
        lines.append(f"--- Finding {index} ---")
        lines.append(f"Resource Type: {resource_type}")

        if finding.get("resource_type") == "ec2":
            lines.append(f"Instance ID: {finding.get('instance_id')}")
            lines.append(f"Instance Type: {finding.get('instance_type')}")
            lines.append(f"State: {finding.get('state')}")
            lines.append(f"Launch Time: {finding.get('launch_time')}")
            lines.append(f"Tags: {finding.get('tags')}")

        elif finding.get("resource_type") == "ebs":
            lines.append(f"Volume ID: {finding.get('volume_id')}")
            lines.append(f"Volume Type: {finding.get('volume_type')}")
            lines.append(f"Size (GB): {finding.get('size')}")
            lines.append(f"State: {finding.get('state')}")
            lines.append(f"Availability Zone: {finding.get('availability_zone')}")
            lines.append(f"Unattached: {finding.get('is_unattached')}")

        lines.append("")

    return "\n".join(lines).rstrip()


def _configure_logging() -> None:
    """Configure root logging for CLI execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """
    Run the scout agent and print findings to stdout.

    Returns:
        0 on success, 1 on failure.
    """
    _configure_logging()

    try:
        agent = ScoutAgent()
        findings = agent.run()

        print("\n=== SCOUT FINDINGS ===\n")
        print(format_findings(findings))
        print(f"\nTotal resources discovered: {len(findings)}")
        return 0

    except AWSConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    except AWSClientError as exc:
        logger.error("AWS error: %s", exc)
        return 1

    except Exception as exc:
        logger.exception("Unexpected scout agent error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
