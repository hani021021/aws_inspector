"""AWS Lambda entry points for the Step Functions workflow.

Each handler gets only the permissions it needs (see infra/lib/remediation-stack.ts).
"""

import boto3

from remediation_agent.scan import scan_state


def check_scan(event: dict, _context) -> dict:
    """Input: {"repository": "...", "tag": "latest"} – output: scan state, count when ready."""
    return scan_state(
        boto3.client("ecr"),
        boto3.client("inspector2"),
        event["repository"],
        event.get("tag", "latest"),
    )
