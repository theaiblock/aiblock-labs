"""Implementation: each thesis -> candidate.py, written by an agent that runs ./check until PASS.

The agent works in a throwaway folder holding the thesis, the contract, a copy of the engine and
the dev-window data only (the sealed year never enters a workspace). It may edit and run code there. The host then re-validates the returned
candidate.py with its own engine; if that fails, the errors go back to the agent for another round.

    python implement.py populations/broad                      # every thesis, same model that wrote it
    python implement.py populations/good --runner codex --impls 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

import engine

# engine.DATA is already resolved; agent workspaces must only see their own dev-window copy
os.environ.pop("ALPHA_DATA_DIR", None)

ROOT = Path(__file__).parent
SCHEMA = ROOT / "implement" / "result.schema.json"
ROUND_TIMEOUT = 1200
LETTERS = "ABCDEFGHIJ"


def dev_files() -> Path:
    """The data files cut at the end of the dev window, written once and copied into every workspace."""
    cache = ROOT / ".cache" / f"dev-{engine.DEV_END}"
    if not (cache / "volume.csv.gz").exists():
        cache.mkdir(parents=True, exist_ok=True)
        for name in ("close", "volume"):
            df = pd.read_csv(engine.DATA / f"{name}.csv.gz", index_col=0, parse_dates=True)
            df.loc[:engine.DEV_END].to_csv(cache / f"{name}.csv.gz")
    return cache


def workspace(thesis: dict, dest: Path) -> None:
    shutil.copytree(dev_files(), dest / "data")
    (dest / "thesis.json").write_text(json.dumps(thesis, indent=2))
    shutil.copy(ROOT / "contract.md", dest)
    shutil.copy(ROOT / "engine.py", dest)
    shutil.copy(ROOT / "implement" / "check.py", dest)
    (dest / "candidate.py").write_text("import numpy as np\nimport pandas as pd\n\n\ndef signal(close, volume, universe):\n    raise NotImplementedError\n")
    check = dest / "check"
    # a warm copy of the host's numba cache: without it every workspace recompiles vectorbt (~15s per
    # ./check), and a sandboxed agent cannot write to the host's own cache
    if (ROOT / ".numba_cache").exists():
        shutil.copytree(ROOT / ".numba_cache", dest / ".numba_cache")
    check.write_text('#!/bin/sh\ncd "$(dirname "$0")" && NUMBA_CACHE_DIR="$PWD/.numba_cache" '
                     f'exec "{sys.executable}" check.py\n')
    check.chmod(0o755)


def run_claude(prompt: str, model: str, cwd: Path) -> tuple[dict, str, float | None]:
    cmd = ["claude", "-p", prompt, "--safe-mode", "--model", model, "--no-session-persistence",
           "--tools", "Bash", "Read", "Write", "Edit",
           "--allowedTools", "Bash(./check)", "Read", "Write", "Edit",
           "--permission-mode", "acceptEdits",
           "--output-format", "json", "--json-schema", SCHEMA.read_text()]
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=ROUND_TIMEOUT, stdin=subprocess.DEVNULL)
    data = json.loads(out.stdout)
    result = data.get("structured_output") or {"status": "blocked", "notes": str(data.get("result"))[:500]}
    # modelUsage comes back empty when the call errors before any model runs (e.g. a usage limit)
    used = max((data.get("modelUsage") or {model: {}}).items(), key=lambda kv: kv[1].get("outputTokens", 0))[0]
    return result, used, data.get("total_cost_usd")


def run_codex(prompt: str, model: str | None, cwd: Path) -> tuple[dict, str, float | None]:
    last = cwd / ".last.json"
    cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "workspace-write",
           "--output-schema", str(SCHEMA), "-o", str(last)] + (["-m", model] if model else [])
    subprocess.run(cmd + [prompt], cwd=cwd, capture_output=True, text=True, timeout=ROUND_TIMEOUT, stdin=subprocess.DEVNULL)
    result = json.loads(last.read_text()) if last.exists() else {"status": "blocked", "notes": "no final message"}
    config = Path.home() / ".codex" / "config.toml"
    used = model or (tomllib.loads(config.read_text()).get("model") if config.exists() else None) or "codex-default"
    return result, used, None


RUNNERS = {"claude": run_claude, "codex": run_codex}


def implement(spec: dict, letter: str, args, out_dir: Path) -> dict:
    runner = args.runner or spec["runner"]
    model = args.model or (spec["model"] if runner == spec["runner"] else None)
    impl_id = f"{spec['spec_id']}.impl-{letter}"
    data = engine.load()
    base = ROOT / "implement" / "prompt.md"
    prompt, rounds, cost, notes, errors, used = base.read_text(), 0, 0.0, "", ["not run"], model
    started = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        workspace(spec["thesis"], ws)
        while rounds < args.max_rounds:
            rounds += 1
            try:
                result, used, c = RUNNERS[runner](prompt, model, ws)
            except subprocess.TimeoutExpired:
                result, c = {"status": "blocked", "notes": f"round timed out after {ROUND_TIMEOUT}s"}, None
            cost += c or 0.0
            notes = result.get("notes", "")
            source = (ws / "candidate.py").read_text()
            errors, _ = engine.validate(source, data)  # host's own engine, not the workspace copy
            if not errors:
                break
            prompt = (base.read_text() + "\n\nThe host re-ran the checks on your `candidate.py` and it failed:\n"
                      + "\n".join(f"- {e}" for e in errors) + "\n\nFix it and run `./check` until it prints PASS.")
    status = "ok" if not errors else "failed"
    record = {"impl_id": impl_id, "spec_id": spec["spec_id"], "idea_id": spec["idea_id"], "runner": runner,
              "model": used, "thesis_model": spec["model"], "status": status, "rounds": rounds,
              "errors": errors, "agent_notes": notes, "cost_usd": round(cost, 4) if runner == "claude" else None,
              "duration_s": round(time.time() - started), "code_sha256": hashlib.sha256(source.encode()).hexdigest(),
              "contract_sha256": hashlib.sha256((ROOT / "contract.md").read_bytes()).hexdigest(),
              "engine_sha256": hashlib.sha256((ROOT / "engine.py").read_bytes()).hexdigest(),
              "finished_at": datetime.now(UTC).isoformat(timespec="seconds")}
    (out_dir / f"{impl_id}.py").write_text(source)
    (out_dir / f"{impl_id}.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{impl_id}: {status} in {rounds} round(s), {record['duration_s']}s" + (f" — {errors[0]}" if errors else ""))
    return record


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("idea_dir", type=Path)
    ap.add_argument("--spec", help="only theses whose spec_id contains this text")
    ap.add_argument("--runner", choices=RUNNERS, help="default: the runner that wrote the thesis")
    ap.add_argument("--model", help="default: the model that wrote the thesis")
    ap.add_argument("--impls", type=int, default=1, help="independent implementations per thesis")
    ap.add_argument("--max-rounds", type=int, default=5, help="host re-validation rounds before giving up")
    ap.add_argument("--concurrency", type=int, default=3)
    args = ap.parse_args()

    specs = [json.loads(p.read_text()) for p in sorted((args.idea_dir / "ideas").glob("*.json"))
             if not args.spec or args.spec in p.stem]
    out_dir = args.idea_dir / "implementations"
    out_dir.mkdir(exist_ok=True)
    jobs = []
    for spec in specs:
        for letter in LETTERS[:args.impls]:
            done = out_dir / f"{spec['spec_id']}.impl-{letter}.json"
            if done.exists() and json.loads(done.read_text())["status"] == "ok":
                continue
            jobs.append((spec, letter))
    print(f"{len(jobs)} implementation(s) to run")
    with ThreadPoolExecutor(args.concurrency) as pool:
        records = list(pool.map(lambda j: implement(j[0], j[1], args, out_dir), jobs))
    ok = sum(r["status"] == "ok" for r in records)
    print(f"{ok}/{len(records)} ok")


if __name__ == "__main__":
    main()
