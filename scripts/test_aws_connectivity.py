"""Safely verify configured AWS credentials with the read-only STS identity API.

Run from the repository root with:
    python scripts/test_aws_connectivity.py

This script does not start the FinOps pipeline or modify AWS resources.
"""

from __future__ import annotations

import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

# Running this file directly puts `scripts/`, rather than the repository root,
# on sys.path. Add the root so the normal `backend` package import works.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.utils.aws_client import (
    AWSClientError,
    AWSConfigurationError,
    AWSClientHelper,
)


def main() -> int:
    try:
        sts = AWSClientHelper().create_client("sts")
        identity = sts.get_caller_identity()
    except (AWSConfigurationError, FileNotFoundError):
        print("AWS credentials are not configured in the project-root .env file.")
        return 1
    except AWSClientError:
        # The client factory intentionally wraps boto exceptions. Do not print
        # exception text because it may contain provider supplied details.
        print("AWS authentication failed; check that the credentials are valid and current.")
        return 1
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {
            "ExpiredToken",
            "ExpiredTokenException",
            "InvalidClientTokenId",
            "UnrecognizedClientException",
            "SignatureDoesNotMatch",
            "TokenRefreshRequired",
        }:
            print("AWS authentication failed; credentials may be expired or invalid.")
        else:
            print("AWS STS identity request failed.")
        return 1
    except BotoCoreError:
        print("Could not connect to AWS STS. Check network connectivity and region configuration.")
        return 1
    except Exception:
        # Keep unexpected exception content out of the console in case it
        # includes credential material from a third-party library.
        print("AWS connectivity check failed unexpectedly.")
        return 1

    print(f"Account ID: {identity['Account']}")
    print(f"ARN: {identity['Arn']}")
    print(f"User ID: {identity['UserId']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
