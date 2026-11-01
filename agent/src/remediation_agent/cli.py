"""Command line entry point.

remediation-agent summarize --repository demo-service
remediation-agent cleanup --repository demo-service [--apply]
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from remediation_agent import cleanup
from remediation_agent.inspector import WrongAccountError, list_active_findings, verify_account
from remediation_agent.prioritize import group_by_package


def direct_dependencies(package_json: Path) -> set[str]:
    manifest = json.loads(package_json.read_text(encoding="utf-8"))
    return set(manifest.get("dependencies", {})) | set(manifest.get("devDependencies", {}))


def run_summarize(args: argparse.Namespace) -> dict:
    findings = list_active_findings(args.repository, args.image_digest)
    deps = direct_dependencies(args.package_json) if args.package_json else None
    groups = group_by_package(findings, deps)
    return {
        "repository": args.repository,
        "findings": len(findings),
        "packages": [asdict(g) | {"finding_count": g.finding_count} for g in groups],
    }


def run_cleanup(args: argparse.Namespace) -> dict:
    protected_tags = [
        t.strip() for t in os.environ.get("PROTECTED_TAGS", "latest").split(",") if t.strip()
    ]
    ecr = cleanup.ecr_client()
    images = cleanup.load_images(ecr, args.repository)
    plan = cleanup.build_plan(images, protected_tags)
    result = {"repository": args.repository, "protected_tags": protected_tags} | asdict(plan)

    if plan.empty:
        result["status"] = "nothing to delete"
    elif not cleanup.protected_scans_ready(ecr, args.repository, images, plan):
        result["status"] = "refused: the protected image is not fully scanned yet"
    elif not args.apply:
        result["status"] = "dry run – run again with --apply after approval"
    else:
        result["deleted"] = cleanup.delete(ecr, args.repository, plan)
        result["status"] = "deleted"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="remediation-agent")
    parser.add_argument(
        "--account-id",
        default=os.environ.get("EXPECTED_AWS_ACCOUNT_ID"),
        help="AWS account the credentials must belong to (default: $EXPECTED_AWS_ACCOUNT_ID)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    summarize = commands.add_parser("summarize", help="Group active findings by package")
    summarize.add_argument("--repository", required=True, help="ECR repository name")
    summarize.add_argument("--image-digest", help="Only this image manifest digest")
    summarize.add_argument(
        "--package-json", type=Path, help="Service package.json, to tell direct from transitive"
    )

    clean = commands.add_parser(
        "cleanup", help="Delete all images except the protected one (dry run by default)"
    )
    clean.add_argument("--repository", required=True, help="ECR repository name")
    clean.add_argument("--apply", action="store_true", help="Delete for real – only after approval")

    args = parser.parse_args()

    if not args.account_id:
        parser.error("set --account-id or EXPECTED_AWS_ACCOUNT_ID")
    try:
        account = verify_account(args.account_id)
    except WrongAccountError as error:
        sys.exit(f"Refusing to run: {error}")
    # stdout carries the JSON result, so status messages go to stderr.
    print(f"Using AWS account {account}", file=sys.stderr)

    result = run_summarize(args) if args.command == "summarize" else run_cleanup(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
