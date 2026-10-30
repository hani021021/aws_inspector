# Architecture

## Workflow

| # | Step | Automated by | Owner |
|---|---|---|---|
| 1 | Fetch findings (ECR / Lambda, fix available) | Inspector API | Code |
| 2 | Analyze: package, direct vs. transitive, prod vs. dev, relevance | Analysis sub-agent | Claude |
| 3 | Determine fixed version, check changelog for breaking changes | Inspector data + analysis sub-agent | Code + Claude |
| 4 | Bump package (incl. `overrides` for transitive deps), run tests, open PR | Fix sub-agent + skills | Claude |
| 5 | Deploy | PR merge = human approval, then existing CI/CD | Human + CI |
| 6 | Delete outdated ECR images that are no longer in use | Cleanup step | Code (+ approval) |
| 7 | Verify finding is closed after rescan, write report | Verification step | Code + Claude |

## Flow

```
Inspector finding
      │  EventBridge
      ▼
Step Functions
  ├─ fetch & filter            (Lambda, deterministic)
  ├─ analyze                   (Lambda, Claude)
  ├─ fix → pull request        (Lambda, Claude + skills)
  ├─ wait for merge + deploy   (human approval)
  ├─ clean up ECR images       (Lambda, deterministic)
  └─ verify & report           (Lambda, deterministic + Claude)
      │
      ▼
DynamoDB audit log · CloudWatch metrics (cost, latency, success rate)
```

## Design principles

- **Workflow first, agent where judgment is needed** – see [ADR 0001](adr/0001-workflow-vs-agent.md).
- **Human in the loop** – no change reaches production without a merged PR.
- **Least privilege** – the agent only has read access to AWS; writes happen via PRs and the existing pipeline.
- **Untrusted input** – finding data and package changelogs are treated as untrusted (prompt injection).
- **Model provider configurable** – Claude API or Amazon Bedrock.
