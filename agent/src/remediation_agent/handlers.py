"""AWS Lambda entry points for the Step Functions workflow.

Each handler gets only the permissions it needs (see infra/lib/remediation-stack.ts).
"""

import base64
import html
import json
import os
from dataclasses import asdict
from urllib.parse import parse_qs, urlencode

import boto3

from remediation_agent import cleanup
from remediation_agent.scan import scan_state


def check_scan(event: dict, _context) -> dict:
    """Input: {"repository": "...", "tag": "latest"} – output: scan state, count when ready."""
    return scan_state(
        boto3.client("ecr"),
        boto3.client("inspector2"),
        event["repository"],
        event.get("tag", "latest"),
    )


def plan_cleanup(event: dict, _context) -> dict:
    """Input: {"repository": "..."} – output: deletion plan with the tags of every image."""
    protected_tags = [t for t in os.environ.get("PROTECTED_TAGS", "latest").split(",") if t]
    images = cleanup.load_images(boto3.client("ecr"), event["repository"])
    plan = cleanup.build_plan(images, protected_tags)
    return {
        "repository": event["repository"],
        "protectedTags": protected_tags,
        "empty": plan.empty,
        "plan": asdict(plan),
        "tags": {i.digest: i.tags for i in images},
    }


def delete_images(event: dict, _context) -> dict:
    """Input: the approved plan from plan_cleanup. Deletes exactly that plan.

    The plan is computed again first: if the repository changed after the approval
    (e.g. a new latest was pushed), nothing is deleted.
    """
    approved = event["plan"]
    ecr = boto3.client("ecr")
    images = cleanup.load_images(ecr, approved["repository"])
    current = cleanup.build_plan(images, approved["protectedTags"])
    if (current.first, current.then) != (approved["plan"]["first"], approved["plan"]["then"]):
        raise RuntimeError("The repository changed after the approval – nothing was deleted.")

    deleted = cleanup.delete(ecr, approved["repository"], current)
    return {
        "deleted": [d["imageDigest"] for d in deleted],
        "summary": f"Deleted {len(deleted)} image(s) from {approved['repository']}; "
        f"kept {len(current.protected)} (protected tags {', '.join(approved['protectedTags'])}).",
    }


def request_approval(event: dict, _context) -> None:
    """Called with a Step Functions task token: e-mails the plan and an approval link.

    The workflow waits until approval_page reports the decision with that token.
    """
    plan, tags = event["plan"]["plan"], event["plan"]["tags"]

    def describe(digest: str) -> str:
        return f"  {digest[:19]}…  {', '.join(tags.get(digest, [])) or '(untagged)'}"

    link = f"{os.environ['APPROVAL_URL']}?{urlencode({'token': event['taskToken']})}"
    message = "\n".join(
        [
            f"The new image in {event['plan']['repository']} is scanned. Delete the old images?",
            "",
            "Delete (indexes first, then their children):",
            *map(describe, plan["first"] + plan["then"]),
            "",
            "Keep (protected tags " + ", ".join(event["plan"]["protectedTags"]) + "):",
            *map(describe, plan["protected"]),
            "",
            f"Approve or reject: {link}",
            "Nothing is deleted without a decision.",
        ]
    )
    boto3.client("sns").publish(
        TopicArn=os.environ["TOPIC_ARN"],
        Subject=f"Approve cleanup of {event['plan']['repository']}",
        Message=message,
    )


def approval_page(event: dict, _context) -> dict:
    """HTTP API handler. GET shows the decision form, POST reports the decision.

    Approving needs a deliberate POST: mail scanners that open links must not approve.
    """
    if event["requestContext"]["http"]["method"] == "GET":
        token = (event.get("queryStringParameters") or {}).get("token", "")
        return _html(
            "<h1>Delete the old images?</h1>"
            '<form method="post">'
            f'<input type="hidden" name="token" value="{html.escape(token)}">'
            '<button name="decision" value="approve">Yes, delete</button> '
            '<button name="decision" value="reject">No, keep them</button>'
            "</form>"
        )

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    form = {k: v[0] for k, v in parse_qs(body).items()}
    approved = form.get("decision") == "approve"
    boto3.client("stepfunctions").send_task_success(
        taskToken=form["token"], output=json.dumps({"approved": approved})
    )
    return _html(
        "<h1>Approved – deleting.</h1>" if approved else "<h1>Rejected – nothing is deleted.</h1>"
    )


def _html(body: str) -> dict:
    return {
        "statusCode": 200,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "body": f"<!doctype html><meta charset='utf-8'><body style='font-family:sans-serif'>{body}",
    }
