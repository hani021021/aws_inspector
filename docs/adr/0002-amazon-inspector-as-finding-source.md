# ADR 0002 – Amazon Inspector as finding source

## Status

Accepted

## Context

The remediation loop mirrors real-world work in enterprise AWS accounts, where Amazon Inspector is the source of vulnerability findings. In the sandbox account (new AWS experience), Inspector requires a Paid plan plus "Activate advanced AWS features". This is irreversible and replaces the hard spend limit with budgets. The project should stay at zero cost.

## Decision

Use **Amazon Inspector (ECR enhanced scanning)** as the only finding source. Findings are read via the Inspector API (`ListFindings`, filtered to `findingStatus = ACTIVE`), and new findings emit an EventBridge event that triggers the remediation workflow.

Cost safeguards:

- Only the `ECR` resource type is enabled (`aws inspector2 enable --resource-types ECR`); EC2, Lambda and code scanning stay off.
- A zero-spend budget in the management account alerts on any charge.
- Inspector runs within the 15-day free trial and is disabled afterwards.

## Consequences

- Covers both operating system packages and language packages (npm), matching what the agent has to fix.
- `ListFindings` also returns `CLOSED` findings of deleted images; every query must filter on status and image digest.
- An image index (BuildKit default) reports `UNSUPPORTED_IMAGE`; Inspector scans its untagged child manifest instead, so findings must be looked up by digest, not by tag.
- Inspector stops reporting OS findings for a discontinued OS 12 months after end of support (e.g. Alpine 3.18). The demo image therefore pins a supported Alpine release (`node:<version>-alpine3.24`). For Alpine, Inspector reports only vulnerabilities the vendor has fixed (Debian also reports open ones), so a missing OS finding means "no pending upgrade", not "no known CVE".
- Findings fall into three sources, identified by `filePath`: direct dependencies, transitive dependencies (`/app/node_modules/…`), and the base image (`/usr/local/lib/node_modules/npm/…`, OS packages). Only the first two can be fixed in `package.json`.
- Verification uses Inspector itself: findings of a deleted image switch to `CLOSED`.

See [manual baseline run](../manual-run.md) for how these were found.
