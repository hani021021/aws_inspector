# Evals

Checks whether the agent keeps the remediation rules – with and without the [remediation skill](../.claude/skills/remediating-inspector-findings/SKILL.md). Every case comes from a mistake that was actually observed during development.

```bash
python evals/run.py                                   # all cases, both variants
python evals/run.py lodash-exact-pin --variant with-skill
```

Each case is a frozen workspace (findings, `package.json`, images …) plus one question. The runner copies the workspace into a temporary directory, adds the skill for the `with-skill` variant and lets Claude Code answer headless (`claude -p`) with read-only tools, no MCP servers and no AWS access. The answer is graded with plain text checks – no model grades another model – and the full run, including every answer, is written to `results/`.

| Case | Observed mistake | Passes when |
|---|---|---|
| `lodash-exact-pin` | `^4.18.1` proposed, `package.json` not read | target 4.18.x, `--save-exact`, no `^`/`~` |
| `aws-commands-name-profile` | delete commands without `--profile` (would hit the default account) | every delete command names profile and region; `latest` and its children are never deleted; index before children |
| `undici-is-base-image` | package bundled with npm treated like an app dependency | no `npm install undici`; fixed in the Dockerfile / base image; npm named as the source |
| `finding-count-not-final` | "0 findings" reported right after the scan turned `ACTIVE` | answer starts with "no"; asks for another query later |

Runs use the Claude Code subscription of whoever runs them (8 short headless sessions per full run).

## Adding a case

1. Create `cases/<id>/workspace/` with the frozen inputs (only data from the sandbox account).
2. Write `cases/<id>/case.json`: `prompt` and `checks` (`present` / `absent` regex, or `lines` – every line matching `select` must match `require` and must not match `forbid`).
3. Keep the answer out of the skill and the prompt; otherwise the case measures copying, not behavior.
