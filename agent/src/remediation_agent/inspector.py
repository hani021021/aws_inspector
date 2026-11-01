"""Reads ACTIVE Inspector findings for one ECR repository (lessons 1 and 2)."""

import boto3

from remediation_agent.prioritize import Finding, from_inspector


class WrongAccountError(RuntimeError):
    pass


def verify_account(expected_account_id: str) -> str:
    """Refuses to run against any account but the expected one.

    The default AWS profile on a developer machine may point to a customer account;
    without this check a missing AWS_PROFILE would silently query it.
    """
    actual = boto3.client("sts").get_caller_identity()["Account"]
    if actual != expected_account_id:
        raise WrongAccountError(
            f"Credentials belong to AWS account {actual}, expected {expected_account_id}. "
            "Check AWS_PROFILE."
        )
    return actual


def list_active_findings(repository: str, image_digest: str | None = None) -> list[Finding]:
    criteria = {
        "findingStatus": [{"comparison": "EQUALS", "value": "ACTIVE"}],
        "resourceType": [{"comparison": "EQUALS", "value": "AWS_ECR_CONTAINER_IMAGE"}],
        "ecrImageRepositoryName": [{"comparison": "EQUALS", "value": repository}],
    }
    if image_digest:
        criteria["ecrImageHash"] = [{"comparison": "EQUALS", "value": image_digest}]

    # Profile and region come from AWS_PROFILE / AWS_REGION, as in the MCP server.
    paginator = boto3.client("inspector2").get_paginator("list_findings")
    return [
        from_inspector(raw)
        for page in paginator.paginate(filterCriteria=criteria)
        for raw in page.get("findings", [])
    ]
