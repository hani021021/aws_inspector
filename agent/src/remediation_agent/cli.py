"""Command line entry point: remediation-agent summarize --repository demo-service"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from remediation_agent.inspector import WrongAccountError, list_active_findings, verify_account
from remediation_agent.prioritize import group_by_package


def direct_dependencies(package_json: Path) -> set[str]:
    manifest = json.loads(package_json.read_text(encoding="utf-8"))
    return set(manifest.get("dependencies", {})) | set(manifest.get("devDependencies", {}))


def main() -> None:
    parser = argparse.ArgumentParser(prog="remediation-agent")
    commands = parser.add_subparsers(dest="command", required=True)
    summarize = commands.add_parser("summarize", help="Group active findings by package")
    summarize.add_argument("--repository", required=True, help="ECR repository name")
    summarize.add_argument("--image-digest", help="Only this image manifest digest")
    summarize.add_argument(
        "--package-json", type=Path, help="Service package.json, to tell direct from transitive"
    )
    summarize.add_argument(
        "--account-id",
        default=os.environ.get("EXPECTED_AWS_ACCOUNT_ID"),
        help="AWS account the credentials must belong to (default: $EXPECTED_AWS_ACCOUNT_ID)",
    )
    args = parser.parse_args()

    if not args.account_id:
        parser.error("set --account-id or EXPECTED_AWS_ACCOUNT_ID")
    try:
        account = verify_account(args.account_id)
    except WrongAccountError as error:
        sys.exit(f"Refusing to run: {error}")
    # stdout carries the JSON result, so status messages go to stderr.
    print(f"Using AWS account {account}", file=sys.stderr)

    findings = list_active_findings(args.repository, args.image_digest)
    deps = direct_dependencies(args.package_json) if args.package_json else None
    groups = group_by_package(findings, deps)

    print(
        json.dumps(
            {
                "repository": args.repository,
                "findings": len(findings),
                "packages": [asdict(g) | {"finding_count": g.finding_count} for g in groups],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
