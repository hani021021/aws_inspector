# Manual baseline run

Before automating anything, the full remediation loop was run once by hand against the sandbox account, for a single package (`axios`). It establishes the baseline the agent is measured against and surfaced the edge cases the agent and its evals have to cover.

- **Date:** 2026-11-01
- **Scope:** `demo-service`, Amazon Inspector (ECR enhanced scanning), eu-north-1
- **Duration:** about 2 hours, including one failed fix attempt

## Run

| Step | What happened |
|---|---|
| 1. Findings | `demo-service:1.0.0` (axios 0.21.1): 95 active findings, 24 of them for axios. |
| 2. Analyze | Direct dependency (`/app/node_modules/axios`). The critical CVE-2026-42043 needs an attacker-controlled URL; `server.js` only calls a fixed URL, so it is not exploitable here – fixed anyway. |
| 3. Fix version | Descriptions list two fix lines (0.x and 1.x). Two CVEs have no 0.x fix, so the 1.x line is required. Highest `fixedInVersion` across all 24 findings: 1.18.0 → chose 1.18.1. |
| 4. Bump | `npm install axios@1.18.1 --save-exact --package-lock-only`, adding 25 transitive packages. |
| 5. Build + push | `1.0.1`, pushed as an image index (BuildKit). |
| 7. Verify | **Failed:** the 24 old findings were gone, but 1.18.1 has 12 CVEs of its own (fixed in 1.20.0). OSV confirmed: 1.18.1 → 12 known vulnerabilities, 1.20.0 → 0. |
| 3–5 (retry) | Bumped to 1.20.0, pushed `1.0.2` (single manifest). 0 axios findings. |
| 6. Clean up | Deleted `1.0.0` and the `1.0.1` index, then the two `1.0.1` child manifests. |
| 7. Verify | All axios findings of the deleted images switched to `CLOSED`; 0 active axios findings remain. |

## Lessons → requirements

| # | Lesson | Goes into |
|---|---|---|
| 1 | `ListFindings` also returns `CLOSED` findings of deleted images. Always filter `findingStatus = ACTIVE`. | MCP tool |
| 2 | Findings are attached to the image manifest digest. For an image index that manifest is untagged, so tag filters miss it – filter by `ecrImageHash`. | MCP tool |
| 3 | An image index reports `UNSUPPORTED_IMAGE`; Inspector scans the child image manifest instead. | MCP tool, eval |
| 4 | `filePath` tells the source: `/app/node_modules/…` (direct or transitive) vs. `/usr/local/lib/node_modules/npm/…` or none (base image). Only the first can be fixed in `package.json`. | Analysis (Claude) |
| 5 | `fixedInVersion` holds one line only; the description may name other lines (e.g. 0.31.1 and 1.15.1). | Analysis (Claude) |
| 6 | The target version itself must be checked against a vulnerability database. Pick the lowest version without known vulnerabilities, not the first `fixedInVersion`. | MCP tool (OSV), eval |
| 7 | Pin exact versions (`--save-exact`), never `^`. | Fix skill |
| 8 | Delete the image index before its children (`ImageReferencedByManifestList` otherwise). Never delete the running image; deletion needs approval. | Cleanup step |
| 9 | Scan and close are asynchronous (`PENDING` → `COMPLETE` → `ACTIVE`; findings still appear after `COMPLETE`, and close minutes after deletion). Compare only once counts are stable. | Verification step |
| 10 | `fixedInVersion` can point to a new major or even a pre-release (express 4.17.1 → `5.0.0-beta.3`) although the current line has a fix. Never propose pre-releases; change the major only if the current line has no fix, and flag it as breaking in the PR. Found after the run, while testing the MCP server. | Analysis (Claude), eval |
