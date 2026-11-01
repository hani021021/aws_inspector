# AWS Inspector Remediation Agent

Automates the manual loop of fixing AWS Inspector package vulnerabilities in container images and Lambda functions:
find → analyze → bump package → open PR → deploy → clean up old ECR images → verify resolved.

Built with Claude (Anthropic API), an MCP server, agent skills and an eval suite, deployed serverless on AWS.

> Status: ✅ M1 – MCP server · next: M2 analysis and prioritization

## The problem

Today this is a manual, repetitive workflow:

1. Open AWS Inspector and review findings
2. Analyze each finding (which package, direct or transitive, actually relevant?)
3. Check whether a fixed version is available
4. Update the package in the service repository
5. Deploy
6. Delete outdated ECR images
7. Re-check Inspector to confirm the finding is resolved

It is time-consuming, easy to postpone and requires context switching between Inspector, the repo, CI/CD and ECR.

## The solution

See [docs/architecture.md](docs/architecture.md). Before automating, the loop was run once by hand – the [manual baseline run](docs/manual-run.md) lists the edge cases the agent has to handle.

## MCP server

A read-only TypeScript MCP server ([`mcp-server/`](mcp-server/)) gives Claude access to Inspector, ECR and the OSV vulnerability database:

| Tool | Purpose |
|---|---|
| `list_active_findings` | Active Inspector findings for an ECR repository, optionally per image digest or package |
| `get_image_scan_status` | Scan status of an image; resolves image indexes to their child manifests |
| `check_package_version` | Known vulnerabilities of an exact npm version (OSV) – used to validate a fix version |
| `list_images` | Images with a deletion plan; images tagged `latest` (configurable) are never deleted |

All tools are read-only. Changes happen through pull requests, deletions need human approval.

Run it with Claude Code:

```bash
cd mcp-server && npm install && npm run build && cd ..
aws login --profile inspector   # any profile with Inspector/ECR read access
claude                          # approve the project MCP server "aws-inspector"
```

Configuration (`.mcp.json`): `AWS_PROFILE` (default `inspector`), `AWS_REGION` (default `eu-north-1`), `PROTECTED_TAGS` (default `latest`) and `EXPECTED_AWS_ACCOUNT_ID` (required). The server refuses to start when the credentials belong to any other account, so a missing profile can never fall back to a different account. Unit tests: `npm test` in `mcp-server/`.

## Agent core (Python)

`agent/` groups active findings per package, tells direct, transitive and base-image packages apart and ranks them, so the model only sees one compact entry per package (71 findings → 18 packages, about 9× less context):

```bash
cd agent
EXPECTED_AWS_ACCOUNT_ID=<account-id> AWS_PROFILE=inspector uv run remediation-agent summarize \
  --repository demo-service --package-json ../sandbox/demo-service/package.json
```

Tests and lint: `uv run pytest`, `uv run ruff check .`

## Repository layout

| Path | Content |
|---|---|
| `agent/` | Python – orchestrator and sub-agents (Anthropic SDK) |
| `mcp-server/` | TypeScript – MCP server with read-only AWS tools (Inspector, ECR) |
| `.claude/skills/` | Agent skills – remediation playbook ([remediating-inspector-findings](.claude/skills/remediating-inspector-findings/SKILL.md)) |
| `infra/` | AWS CDK – Step Functions, Lambda, DynamoDB |
| `sandbox/` | Deliberately vulnerable demo service + ECR repository |
| `evals/` | Golden dataset and eval runner |
| `docs/` | Architecture, ADRs, deployment playbook |

## Roadmap

- [x] **M0** Setup – repo, AWS sandbox account, budget alarm, Inspector, manual baseline run
- [x] **M1** MCP server – Inspector findings, ECR scan status and images, OSV version check
- [ ] **M2** Analysis and prioritization (incl. Claude API key)
- [ ] **M3** Fix agent – package bump, tests, pull request (with skills)
- [ ] **M4** Evals – golden dataset, LLM-as-judge, CI gate
- [ ] **M5** Cleanup, verification and serverless deployment
- [ ] **M6** Case study and demo

## Results

Baseline: fixing one package (axios, 24 findings) by hand took about 2 hours, including one failed attempt.

First agent run (Claude Code with the MCP server and the remediation skill): lodash, 5 findings – analysis, exact version bump and a documented pull request ([#1](https://github.com/hani021021/aws_inspector/pull/1)) in under 2 minutes; after merge, deploy and approved cleanup all lodash findings were `CLOSED`. Without the skill the same question produced a `^` range and no `package.json` check.

_To be filled after M5: time saved per finding, fix success rate, eval scores, cost per run._
