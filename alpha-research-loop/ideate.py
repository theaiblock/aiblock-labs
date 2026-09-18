"""Idea generation: N independent model calls on one research idea -> N thesis JSON files.

Each call is a separate process in an empty temp directory with no tools and no session, so no
sample can see another. Works with `claude -p` and `codex exec`.

    python ideate.py ideas/broad.md --runner claude --n 20
    python ideate.py ideas/good.md --runner codex --n 20 --model gpt-5.6-sol
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import tempfile
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parent
SCHEMA_PATH = ROOT / "ideate" / "thesis.schema.json"
TIMEOUT = 600
DEFAULT_MODEL = {"claude": "claude-opus-5", "codex": None}  # codex: use ~/.codex/config.toml


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_prompt(idea: str) -> str:
    template = (ROOT / "ideate" / "prompt.md").read_text()
    return (template.replace("{idea}", idea.strip())
            .replace("{universe}", (ROOT / "universe.md").read_text().strip())
            .replace("{contract}", (ROOT / "contract.md").read_text().strip()))


def validate(obj, schema, path="thesis") -> None:
    kind = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float)}
    if not isinstance(obj, checks[kind]) or (kind in ("integer", "number") and isinstance(obj, bool)):
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and obj not in schema["enum"]:
        raise ValueError(f"{path}: {obj!r} not in {schema['enum']}")
    if kind == "object":
        missing = set(schema["required"]) - obj.keys()
        extra = obj.keys() - schema["properties"].keys()
        if missing or extra:
            raise ValueError(f"{path}: missing {sorted(missing)} extra {sorted(extra)}")
        for key, sub in schema["properties"].items():
            validate(obj[key], sub, f"{path}.{key}")
    if kind == "array":
        for i, item in enumerate(obj):
            validate(item, schema["items"], f"{path}[{i}]")


def call_claude(prompt: str, model: str | None, cwd: str, schema_path: Path = SCHEMA_PATH) -> tuple[dict, str, float | None]:
    cmd = ["claude", "-p", prompt, "--safe-mode", "--tools", "", "--no-session-persistence",
           "--output-format", "json", "--json-schema", schema_path.read_text()]
    if model:
        cmd += ["--model", model]
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT,
                         stdin=subprocess.DEVNULL, check=True)
    data = json.loads(out.stdout)
    if data.get("is_error") or "structured_output" not in data:
        raise RuntimeError(f"claude error: {data.get('result')}")
    # modelUsage also lists small background models; the answering model wrote the most tokens
    used = max(data["modelUsage"].items(), key=lambda kv: kv[1].get("outputTokens", 0))[0]
    return data["structured_output"], used, data.get("total_cost_usd")


def call_codex(prompt: str, model: str | None, cwd: str, schema_path: Path = SCHEMA_PATH) -> tuple[dict, str, float | None]:
    last = Path(cwd) / "last.json"
    cmd = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
           "--output-schema", str(schema_path), "-o", str(last)]
    if model:
        cmd += ["-m", model]
    subprocess.run(cmd + [prompt], cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT,
                   stdin=subprocess.DEVNULL, check=True)
    # codex does not report the model it used, so record the one requested or configured
    config = Path.home() / ".codex" / "config.toml"
    used = model or (tomllib.loads(config.read_text()).get("model") if config.exists() else None) or "codex-default"
    return json.loads(last.read_text()), used, None


RUNNERS = {"claude": call_claude, "codex": call_codex}


def sample(i: int, args, prompt: str, schema: dict, meta: dict, out_dir: Path) -> dict:
    error = None
    for attempt in range(2):
        try:
            with tempfile.TemporaryDirectory() as cwd:
                thesis, model, cost = RUNNERS[args.runner](prompt, args.model, cwd)
            validate(thesis, schema)
            spec_id = f"{meta['run_id']}-{i:03d}"
            record = {"spec_id": spec_id, **meta, "runner": args.runner, "model": model,
                      "sample": i, "attempts": attempt + 1, "cost_usd": cost,
                      "generated_at": datetime.now(UTC).isoformat(timespec="seconds"), "thesis": thesis}
            (out_dir / "ideas" / f"{spec_id}.json").write_text(json.dumps(record, indent=2) + "\n")
            return record
        except Exception as exc:  # recorded, never silently dropped
            error = f"{type(exc).__name__}: {exc}"[:500]
    return {"sample": i, "error": error}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("idea", type=Path)
    ap.add_argument("--runner", choices=RUNNERS, required=True)
    ap.add_argument("--model", help="model id passed to the runner (default: claude-opus-5 / codex config)")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--out", type=Path, default=ROOT / "populations")
    args = ap.parse_args()
    args.model = args.model or DEFAULT_MODEL[args.runner]

    idea_id = args.idea.stem
    prompt = build_prompt(args.idea.read_text())
    schema = json.loads(SCHEMA_PATH.read_text())
    # one folder per idea; every model's theses land side by side in ideas/, identified inside the JSON
    out_dir = args.out / idea_id
    (out_dir / "ideas").mkdir(parents=True, exist_ok=True)
    prompt_sha = sha(prompt)
    prompt_file = out_dir / f"prompt-{prompt_sha[:8]}.md"
    if not prompt_file.exists():
        prompt_file.write_text(prompt)
    run_id = f"{idea_id}-{args.runner}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    meta = {"idea_id": idea_id, "run_id": run_id, "prompt_sha256": prompt_sha,
            "contract_sha256": sha((ROOT / "contract.md").read_text()),
            "universe_sha256": sha((ROOT / "universe.md").read_text())}

    with ThreadPoolExecutor(args.concurrency) as pool:
        results = list(pool.map(lambda i: sample(i, args, prompt, schema, meta, out_dir), range(args.n)))

    ok = [r for r in results if "error" not in r]
    costs = [r["cost_usd"] for r in ok if r["cost_usd"] is not None]
    run = {**meta, "runner": args.runner, "requested_model": args.model,
           "models": sorted({r["model"] for r in ok}), "n_requested": args.n, "n_valid": len(ok),
           "failures": [r for r in results if "error" in r],
           "cost_usd": round(sum(costs), 4) if costs else None,
           "finished_at": datetime.now(UTC).isoformat(timespec="seconds")}
    with open(out_dir / "runs.jsonl", "a") as log:  # runs of different models may finish together
        fcntl.flock(log, fcntl.LOCK_EX)
        log.write(json.dumps(run) + "\n")
    print(f"{run_id}: {len(ok)}/{args.n} valid, models {run['models']}, cost {run['cost_usd']}")


if __name__ == "__main__":
    main()
