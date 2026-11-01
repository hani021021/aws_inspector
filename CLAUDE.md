# CLAUDE.md

Remediation agent for Amazon Inspector findings in ECR images. Start with [README.md](README.md), [docs/architecture.md](docs/architecture.md) and the lessons in [docs/manual-run.md](docs/manual-run.md). For remediation work, follow the `remediating-inspector-findings` skill.

## Environment rules

- Never change the global npm configuration (no `npm config fix`, `npm config set`, edits to the user `.npmrc`) – it belongs to another project. Run npm with an empty user config instead: `$env:npm_config_userconfig = "$env:TEMP\empty.npmrc"` (PowerShell), or `--userconfig` on single commands.
- AWS only through the sandbox profile: `AWS_PROFILE=inspector`, `AWS_REGION=eu-north-1`, and `EXPECTED_AWS_ACCOUNT_ID` set. The default AWS profile is a different account – never fall back to it, and never fill in the account ID yourself. Every AWS CLI command you run or print includes `--profile inspector --region eu-north-1`.
- Never use code, data or details from customer projects.
- Deleting ECR images, pushing images and pushing to git need explicit approval.

## Commands

| Part | Build / run | Test |
|---|---|---|
| `mcp-server/` (TypeScript) | `npm run build` | `npm test` |
| `agent/` (Python, uv) | `uv run remediation-agent summarize --repository demo-service` | `uv run pytest`, `uv run ruff check .` |
| `sandbox/demo-service/` | see its README (Docker, ECR push) | – |

## Conventions

- Pin exact dependency versions.
- Conventional Commits; no `Co-Authored-By` trailer.
- Keep test data out of prompts and skills – examples in the skill must not contain answers to eval cases.
