"""Runs the agent evals: every case with and without the remediation skill.

Each case is a frozen workspace (findings, package.json, ...) plus a question. Claude Code
answers it headless (`claude -p`, read-only tools, no MCP servers, no AWS access) and the
answer is graded with simple text checks. Usage:

    python evals/run.py                 # all cases, both variants
    python evals/run.py lodash-exact-pin --variant with-skill
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "evals" / "cases"
SKILL = ROOT / ".claude" / "skills" / "remediating-inspector-findings"
RESULTS = ROOT / "evals" / "results"
VARIANTS = ("without-skill", "with-skill")


def check(answer: str, spec: dict) -> bool:
    kind, pattern = spec["type"], spec.get("pattern")
    flags = re.IGNORECASE | re.MULTILINE
    if kind == "present":
        return re.search(pattern, answer, flags) is not None
    if kind == "absent":
        return re.search(pattern, answer, flags) is None
    if kind == "lines":  # every line matching `select` must match `require` and not `forbid`
        # Join shell line continuations (bash `\`, PowerShell backtick) into one command line.
        # A closing or opening ``` fence is not a continuation.
        joined = re.sub(r"(?<!`)[`\\][ \t]*\r?\n[ \t]*", " ", answer)
        lines = [line for line in joined.splitlines() if re.search(spec["select"], line, flags)]
        return bool(lines) and all(
            re.search(spec.get("require", ""), line, flags)
            and not (spec.get("forbid") and re.search(spec["forbid"], line, flags))
            for line in lines
        )
    raise ValueError(f"unknown check type {kind}")


def run_case(case_dir: Path, variant: str) -> dict:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
        workspace = Path(tmp)
        shutil.copytree(case_dir / "workspace", workspace, dirs_exist_ok=True)
        if variant == "with-skill":
            shutil.copytree(SKILL, workspace / ".claude" / "skills" / SKILL.name)

        completed = subprocess.run(
            [
                shutil.which("claude") or "claude",
                "-p",
                case["prompt"],
                "--output-format",
                "json",
                "--allowedTools",
                "Read,Glob,Grep,Skill",
                "--strict-mcp-config",
                "--no-session-persistence",
            ],
            cwd=workspace,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
    try:
        output = json.loads(completed.stdout)
    except json.JSONDecodeError:
        output = {"result": completed.stdout + completed.stderr, "is_error": True}

    result = {
        "case": case_dir.name,
        "variant": variant,
        "duration_s": round(output.get("duration_ms", 0) / 1000),
        "answer": output.get("result") or "",
    }
    return grade(result)


def grade(result: dict) -> dict:
    """(Re-)grades a stored answer, so changed checks need no new model run."""
    case = json.loads((CASES / result["case"] / "case.json").read_text(encoding="utf-8"))
    checks = [{"name": c["name"], "passed": check(result["answer"], c)} for c in case["checks"]]
    return result | {
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*", help="case ids (default: all)")
    parser.add_argument("--variant", choices=VARIANTS, action="append")
    parser.add_argument("--regrade", type=Path, help="re-grade a stored results file instead")
    args = parser.parse_args()

    if args.regrade:
        stored = json.loads(args.regrade.read_text(encoding="utf-8"))
        results = [grade(r) for r in stored]
        args.regrade.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        report(results)
        return

    case_dirs = [CASES / c for c in args.cases] if args.cases else sorted(CASES.iterdir())
    results = []
    for case_dir in case_dirs:
        for variant in args.variant or VARIANTS:
            print(f"running {case_dir.name} ({variant}) ...", file=sys.stderr, flush=True)
            results.append(run_case(case_dir, variant))

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    (RESULTS / f"{stamp}.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    report(results)


def report(results: list[dict]) -> None:
    for r in results:
        failed = [c["name"] for c in r["checks"] if not c["passed"]]
        if failed:
            print(f"FAILED {r['case']} ({r['variant']}): {', '.join(failed)}")

    print(f"\n{'case':<28}{'without skill':>15}{'with skill':>13}")
    for name in dict.fromkeys(r["case"] for r in results):
        row = {r["variant"]: f"{r['passed']}/{r['total']}" for r in results if r["case"] == name}
        print(f"{name:<28}{row.get('without-skill', '-'):>15}{row.get('with-skill', '-'):>13}")
    for variant in VARIANTS:
        selected = [r for r in results if r["variant"] == variant]
        if selected:
            score = sum(r["passed"] for r in selected) / sum(r["total"] for r in selected)
            print(f"{variant:<28}{score:>15.0%}")


if __name__ == "__main__":
    main()
