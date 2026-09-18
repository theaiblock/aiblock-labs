"""Backtest: every valid implementation -> result JSON, scored by the locked engine. No model involved.

    python backtest.py populations/broad                  # dev window, 2021-01-01 → 2025-08-31
    python backtest.py populations/broad --window sealed  # the sealed year; logged in SEALED_LOG.jsonl

The dev window is what the loop learns from. The sealed year (2025-09-01 → 2026-08-31) is scored
into its own folder, and every opening is logged, so it is visible how many times it was looked at.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import engine
from stats import paired

import pandas as pd

ROOT = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("idea_dir", type=Path)
    ap.add_argument("--window", choices=engine.WINDOWS, default="dev")
    ap.add_argument("--force", action="store_true", help="re-score results that already exist")
    args = ap.parse_args()
    data = engine.load(end=None if args.window == "sealed" else engine.DEV_END)
    engine_sha = hashlib.sha256((ROOT / "engine.py").read_bytes()).hexdigest()

    ideas, impls = args.idea_dir / "ideas", args.idea_dir / "implementations"
    out_dir = args.idea_dir / ("backtests" if args.window == "dev" else "backtests-sealed")
    out_dir.mkdir(exist_ok=True)
    if args.window == "sealed":
        with open(ROOT / "SEALED_LOG.jsonl", "a") as log:
            log.write(json.dumps({"opened_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                  "population": str(args.idea_dir), "engine_sha256": engine_sha}) + "\n")

    bench_path = out_dir / "benchmark.result.json"
    if args.force or not bench_path.exists():
        _, w = engine.validate((ROOT / "implement" / "benchmark_signal.py").read_text(), data)
        bench_path.write_text(json.dumps({"id": "benchmark", "engine_sha256": engine_sha, **engine.score(w, data, args.window)}) + "\n")
    bench = json.loads(bench_path.read_text())
    bench_r = pd.Series(bench["daily_returns"])

    rows = []
    for impl_path in sorted(impls.glob("*.impl-*.json")):
        impl = json.loads(impl_path.read_text())
        out = out_dir / f"{impl['impl_id']}.result.json"
        if impl["status"] != "ok":
            continue
        if args.force or not out.exists():
            source = (impls / f"{impl['impl_id']}.py").read_text()
            errors, w = engine.validate(source, data)
            result = {"impl_id": impl["impl_id"], "spec_id": impl["spec_id"], "model": impl["model"],
                      "code_sha256": hashlib.sha256(source.encode()).hexdigest(), "engine_sha256": engine_sha}
            if errors:
                result["errors"] = errors
            else:
                result |= engine.score(w, data, args.window)
                result["vs_benchmark"] = paired(pd.Series(result["daily_returns"]), bench_r)
            out.write_text(json.dumps(result) + "\n")
        result = json.loads(out.read_text())
        spec = json.loads((ideas / f"{impl['spec_id']}.json").read_text())
        rows.append((result.get("sharpe", float("nan")), result.get("vs_benchmark", {}), impl["impl_id"],
                     impl["model"], spec["thesis"]["title"]))

    print(f"benchmark sharpe {bench['sharpe']:.2f}  ({args.window}: {bench['period'][0]} → {bench['period'][1]})")
    for sharpe, vs, impl_id, model, title in sorted(rows, key=lambda r: -r[0]):
        ci = f"ΔSR {vs['delta_sharpe']:+.2f} [{vs['ci_low']:+.2f}, {vs['ci_high']:+.2f}] {vs['verdict']:7}" if vs else ""
        print(f"  {sharpe:5.2f}  {ci}  {model:18s} {title}  [{impl_id}]")


if __name__ == "__main__":
    main()
