# /// script
# dependencies = ["diagrams==0.25.1"]
# ///
"""Technical architecture diagram as code.

Lays out the system on a fixed grid and writes docs/architecture-detailed.svg with the
official AWS architecture icons (bundled with the `diagrams` package) embedded:

    uv run docs/diagrams/architecture.py
"""

import base64
import html
import itertools
from pathlib import Path

import diagrams
from diagrams.aws.compute import ECR, Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import EventbridgeRule, SimpleNotificationServiceSns, StepFunctions
from diagrams.aws.network import APIGateway
from diagrams.aws.security import IAMAWSSts, IAMRole, IdentityAndAccessManagementIam, Inspector
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.client import Client, User
from diagrams.onprem.network import Internet
from diagrams.onprem.vcs import Github
from diagrams.programming.language import Python, TypeScript

OUTPUT = Path(__file__).resolve().parent.parent / "architecture-detailed.svg"
RESOURCES = Path(diagrams.__file__).resolve().parent.parent
WIDTH, HEIGHT = 1760, 1330

COLORS = {
    "data": "#475569",
    "auth": "#7c3aed",
    "human": "#059669",
}

parts: list[str] = []


def icon_uri(node_class) -> str:
    path = RESOURCES / node_class._icon_dir / node_class._icon
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def text(x, y, content, size=13, weight=400, color="#1f2937", anchor="middle", halo=False):
    halo_attrs = ' stroke="#ffffff" stroke-width="5" paint-order="stroke"' if halo else ""
    parts.append(
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'text-anchor="{anchor}"{halo_attrs}>{html.escape(content)}</text>'
    )


def node(node_class, cx, cy, lines, size=56):
    parts.append(
        f'<image href="{icon_uri(node_class)}" x="{cx - size / 2}" y="{cy - size / 2}" '
        f'width="{size}" height="{size}"/>'
    )
    for i, line in enumerate(lines):
        first = i == 0
        text(
            cx,
            cy + size / 2 + 18 + i * 16,
            line,
            size=13 if first else 12,
            weight=600 if first else 400,
            color="#111827" if first else "#4b5563",
        )


def zone(x, y, w, h, title, stroke, fill, dashed=False):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.6"{dash}/>'
    )
    if title:
        text(x + 16, y + 24, title, size=14.5, weight=700, color=stroke, anchor="start")


def badge(cx, cy, number, color):
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="11" fill="{color}"/>')
    text(cx, cy + 4, str(number), size=11.5, weight=700, color="#ffffff")


def arrow(points, kind="data", label=None, at=None, anchor="middle", step=None, step_at=None):
    color = COLORS[kind]
    dash = ' stroke-dasharray="7 5"' if kind == "auth" else ""
    width = 2.6 if kind == "human" else 2
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    parts.append(
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash} '
        f'stroke-linejoin="round" marker-end="url(#arrow-{kind})"/>'
    )
    if label:
        for i, line in enumerate(label.split("\n")):
            text(at[0], at[1] + i * 15, line, 12, 600, color, anchor, halo=True)
    if step:
        badge(*step_at, step, color)


# ---------------------------------------------------------------- title
text(
    40, 46, "AWS Inspector Remediation Agent — technical architecture", 26, 700, "#111827", "start"
)
text(
    40,
    74,
    "Which AWS services and tools take part, how they talk to each other and how each of them "
    "authenticates",
    15,
    400,
    "#4b5563",
    "start",
)

# ---------------------------------------------------------------- top row
zone(40, 120, 160, 170, None, "#9ca3af", "#f9fafb", dashed=True)
node(Internet, 120, 190, ["OSV.dev API", "public, no auth"], size=52)

zone(230, 110, 720, 190, "Developer workstation", "#4338ca", "#eef2ff")
node(TypeScript, 340, 197, ["MCP server aws-inspector", "read-only tools"])
node(Client, 590, 197, ["Claude Code", "agent + remediation skill"])
node(Python, 830, 197, ["remediation-agent CLI", "summarize · cleanup"])

zone(990, 110, 520, 190, "GitHub", "#111827", "#f3f4f6")
node(GithubActions, 1110, 197, ["GitHub Actions", "build-demo-service"])
node(Github, 1390, 197, ["Repository", "pull requests"])

node(User, 1640, 197, ["Reviewer", "approves the deploy"])

# ---------------------------------------------------------------- AWS account
zone(
    40,
    340,
    1490,
    590,
    "AWS account · eu-north-1 · deployed with AWS CDK (AWS CloudFormation)",
    "#c2410c",
    "#fff7ed",
)

zone(230, 390, 520, 175, "Registry and scanning", "#c2410c", "#ffffff")
node(Inspector, 340, 480, ["Amazon Inspector", "continuous scan"])
node(ECR, 620, 480, ["Amazon ECR", "demo-service"])
node(EventbridgeRule, 860, 480, ["Amazon EventBridge", "rule: push of latest"])

zone(990, 390, 520, 175, "Identity — no stored keys", "#6d28d9", "#f5f3ff")
node(IdentityAndAccessManagementIam, 1110, 480, ["AWS IAM", "OIDC provider (GitHub)"])
node(IAMAWSSts, 1270, 480, ["AWS STS", "1-hour credentials"])
node(IAMRole, 1430, 480, ["IAM role", "GitHubPushRole"])

zone(230, 600, 1280, 305, None, "#c2410c", "#ffffff")
parts.append(f'<image href="{icon_uri(StepFunctions)}" x="244" y="610" width="30" height="30"/>')
text(
    284,
    631,
    "AWS Step Functions — cleanup workflow · one IAM role per Lambda",
    14.5,
    700,
    "#c2410c",
    "start",
)

steps = [
    (Lambda, 340, ["AWS Lambda", "CheckScan", "waits for a stable scan"]),
    (Lambda, 560, ["AWS Lambda", "PlanCleanup", "all images except latest"]),
    (Lambda, 780, ["AWS Lambda", "RequestApproval", "waits for a decision"]),
    (Dynamodb, 1000, ["Amazon DynamoDB", "audit log", "records the decision"]),
    (Lambda, 1220, ["AWS Lambda", "DeleteImages", "ecr:BatchDeleteImage"]),
]
for node_class, cx, lines in steps:
    node(node_class, cx, 690, lines)
for (_, a, _), (_, b, _) in itertools.pairwise(steps):
    arrow([(a + 34, 690), (b - 34, 690)])

node(SimpleNotificationServiceSns, 780, 832, ["Amazon SNS", "e-mail"], size=48)
node(APIGateway, 1000, 832, ["Amazon API Gateway", "→ AWS Lambda ApprovalPage"], size=48)

node(User, 890, 1015, ["Reviewer", "approves the cleanup"])

# ---------------------------------------------------------------- arrows
arrow([(560, 197), (372, 197)], label="stdio", at=(466, 188))
arrow([(312, 197), (204, 197)], label="version", at=(258, 222), step=3, step_at=(258, 197))
arrow(
    [(590, 167), (590, 148), (1390, 148), (1390, 165)],
    "auth",
    label="git push · gh pr create (OAuth token)",
    at=(760, 141),
    step=4,
    step_at=(640, 148),
)
arrow(
    [(1612, 197), (1422, 197)],
    "human",
    label="review + merge",
    at=(1517, 186),
    step=5,
    step_at=(1517, 197),
)
arrow(
    [(1362, 197), (1142, 197)], label="on push to main", at=(1250, 186), step=6, step_at=(1250, 197)
)

arrow(
    [(340, 227), (340, 449)],
    "auth",
    label="ListFindings, DescribeImages\n(aws login, account check)",
    at=(354, 318),
    anchor="start",
    step=2,
    step_at=(340, 330),
)
arrow([(372, 480), (588, 480)], label="scans images", at=(480, 470), step=1, step_at=(480, 480))
arrow(
    [(1082, 205), (970, 205), (970, 322), (620, 322), (620, 449)],
    label="docker push :sha, :latest",
    at=(795, 314),
    step=8,
    step_at=(970, 270),
)
arrow(
    [(1110, 227), (1110, 449)],
    "auth",
    label="OIDC token",
    at=(1124, 338),
    anchor="start",
    step=7,
    step_at=(1110, 330),
)
arrow([(1140, 480), (1240, 480)], "auth")
arrow([(1300, 480), (1400, 480)], "auth")
arrow([(652, 480), (828, 480)], label="push event", at=(740, 470), step=9, step_at=(740, 480))
arrow(
    [(860, 545), (860, 598)],
    label="StartExecution",
    at=(874, 578),
    anchor="start",
    step=10,
    step_at=(860, 572),
)
arrow([(780, 772), (780, 806)], step=11, step_at=(806, 789))
text(822, 793, "publish", 12, 600, COLORS["data"], "start", halo=True)
arrow(
    [(760, 896), (760, 1015), (860, 1015)],
    "human",
    label="e-mail: plan + link",
    at=(690, 990),
    step=12,
    step_at=(760, 960),
)
arrow(
    [(920, 1015), (1000, 1015), (1000, 892)],
    "human",
    label="approve (POST)",
    at=(1084, 990),
    step=13,
    step_at=(1000, 960),
)
arrow(
    [(1000, 806), (1000, 774)],
    "auth",
    label="SendTaskSuccess (task token)",
    at=(1016, 794),
    anchor="start",
)
badge(1256, 664, 14, COLORS["data"])

# ---------------------------------------------------------------- legend
text(40, 1112, "Legend", 16, 700, "#111827", "start")
for i, (kind, label) in enumerate(
    [("data", "API call or data"), ("auth", "authentication"), ("human", "human approval")]
):
    y = 1140 + i * 28
    arrow([(40, y), (110, y)], kind)
    text(122, y + 4, label, 13, 400, "#1f2937", "start")
badge(51, 1224, "n", COLORS["data"])
text(70, 1228, "step in the order of the flow", 13, 400, "#1f2937", "start")

text(420, 1112, "Authentication", 16, 700, "#111827", "start")
for i, (who, how) in enumerate(
    [
        (
            "Developer → AWS",
            (
                "aws login (browser) gives a short-lived session; every tool checks "
                "the account with AWS STS"
            ),
        ),
        ("Agent → GitHub", "gh CLI with an OAuth token kept in the operating system's keyring"),
        (
            "GitHub Actions → AWS",
            ("OIDC token → AWS STS AssumeRoleWithWebIdentity → IAM role: 1 hour, ECR push only"),
        ),
        (
            "Workflow → AWS",
            (
                "one IAM execution role per Lambda; only DeleteImages may delete, only "
                "in demo-service"
            ),
        ),
        (
            "Approval",
            ("Step Functions task token in the e-mail link; only a POST from the form decides"),
        ),
    ]
):
    y = 1144 + i * 26
    text(420, y, who, 13, 700, "#111827", "start")
    text(600, y, how, 13, 400, "#374151", "start")

# ---------------------------------------------------------------- write
markers = "".join(
    f'<marker id="arrow-{kind}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
    f'markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/>'
    "</marker>"
    for kind, color in COLORS.items()
)
OUTPUT.write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" '
    f'height="{HEIGHT}" font-family="Segoe UI, -apple-system, Helvetica, Arial, sans-serif">'
    "<title>AWS Inspector Remediation Agent – technical architecture</title>"
    f"<defs>{markers}</defs>"
    f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>' + "".join(parts) + "</svg>\n",
    encoding="utf-8",
)
print(f"wrote {OUTPUT}")
