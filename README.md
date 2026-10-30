# AWS Inspector Remediation Agent

Automates the manual loop of fixing AWS Inspector package vulnerabilities in container images and Lambda functions:
find → analyze → bump package → open PR → deploy → clean up old ECR images → verify resolved.

Built with Claude (Anthropic API), an MCP server, agent skills and an eval suite, deployed serverless on AWS.

> Status: 🚧 M0 – project setup

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

See [docs/architecture.md](docs/architecture.md).

## Repository layout

| Path | Content |
|---|---|
| `agent/` | Python – orchestrator and sub-agents (Anthropic SDK) |
| `mcp-server/` | TypeScript – MCP server with read-only AWS tools (Inspector, ECR) |
| `skills/` | Agent skills – remediation playbooks |
| `infra/` | AWS CDK – Step Functions, Lambda, DynamoDB |
| `sandbox/` | Deliberately vulnerable demo service + ECR repository |
| `evals/` | Golden dataset and eval runner |
| `docs/` | Architecture, ADRs, deployment playbook |

## Roadmap

- [ ] **M0** Setup – repo, AWS sandbox account, budget alarm, API key
- [ ] **M1** MCP server – Inspector findings, ECR and repo context
- [ ] **M2** Analysis and prioritization
- [ ] **M3** Fix agent – package bump, tests, pull request (with skills)
- [ ] **M4** Evals – golden dataset, LLM-as-judge, CI gate
- [ ] **M5** Cleanup, verification and serverless deployment
- [ ] **M6** Case study and demo

## Results

_To be filled after M5: time saved per finding, fix success rate, eval scores, cost per run._
