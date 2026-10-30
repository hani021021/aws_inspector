# ADR 0001 – Deterministic workflow with targeted LLM steps

## Status

Accepted

## Context

The remediation loop has steps that are fully deterministic (fetching findings, deleting ECR images, polling for scan results) and steps that require judgment (is the vulnerable package actually used in production, how to fix a transitive dependency, does the fixed version introduce breaking changes).

## Decision

Orchestrate the loop as a deterministic workflow (Step Functions). Use Claude only for the judgment steps: analysis, fix strategy, code change and PR description, final report.

## Consequences

- Predictable cost and behavior; each LLM step can be evaluated in isolation.
- Failures are easy to localize and retry per step.
- Less flexible than a single autonomous agent – acceptable, because the process is well understood.
