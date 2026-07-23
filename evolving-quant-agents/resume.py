#!/usr/bin/env python3
"""Resume the evolution runs after a subscription-limit stop — built for the reality
that `headless/claude` WILL hit the limit mid-run.

ShinkaEvolve auto-resumes: point it at an existing results_dir and it restores the population
and continues from the last completed generation. This wrapper drives that per mode, reports
progress from programs.sqlite, and — the important part — detects the limit signal (a batch
that adds 0 programs, because the CLI returned empty "None" responses) and STOPS CLEANLY with
a clear "re-run when your sub resets" message instead of burning retries into the wall.

Usage (run when your subscription has budget):
    python resume.py                         # resume naive then honest to --target, cheap config
    python resume.py --modes honest          # just one mode
    python resume.py --target 12             # generations to reach per mode
    python resume.py --watch --sleep 1800    # keep retrying every 30 min until both reach target

Nothing runs until you invoke this. Progress is never lost — it accumulates in runs/<mode>/.
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent
RUN_EVOLVE = TASK_DIR / "run_evolve.py"


def gens_done(mode: str) -> int:
    """Completed generations in a run (max generation index + 1; 0 if none)."""
    db = TASK_DIR / "runs" / mode / "programs.sqlite"
    if not db.exists():
        return 0
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        mg = con.execute("SELECT MAX(generation) FROM programs").fetchone()[0]
        con.close()
        return 0 if mg is None else int(mg) + 1
    except Exception:
        return 0


def resume_mode(mode: str, target: int, model: str, effort: str, max_tokens: int,
                meta_model: str, meta_interval: int) -> tuple[int, int]:
    """One resume attempt for a mode. Returns (before, after) completed-generation counts."""
    before = gens_done(mode)
    if before >= target:
        print(f"[{mode}] already at {before}/{target} generations — nothing to do.")
        return before, before

    print(f"[{mode}] resuming from generation {before} toward {target} "
          f"(mutate={model} meta={meta_model or 'off'}) ...")
    cmd = [
        sys.executable, str(RUN_EVOLVE), "--mode", mode,
        "--generations", str(target),
        "--results-dir", str(TASK_DIR / "runs" / mode),
        "--model", model, "--effort", effort, "--max-tokens", str(max_tokens),
        "--meta-model", meta_model, "--meta-interval", str(meta_interval),
    ]
    log = TASK_DIR / "runs" / f"{mode}.resume.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(f"\n\n===== resume {time.strftime('%Y-%m-%d %H:%M:%S')} "
                 f"from gen {before} -> {target} =====\n")
        subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, check=False)

    after = gens_done(mode)
    added = after - before
    if added > 0:
        print(f"[{mode}] +{added} generations -> now {after}/{target}. (log: {log.name})")
    else:
        print(f"[{mode}] added 0 generations — this is the subscription-limit signal "
              f"(empty LLM responses). Re-run resume.py when your sub resets. (log: {log.name})")
    return before, after


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modes", default="naive,honest", help="comma list: naive,honest")
    ap.add_argument("--target", type=int, default=10, help="generations to reach per mode")
    ap.add_argument("--model", default="headless/claude@sonnet", help="mutation model (cheap)")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh"])
    ap.add_argument("--max-tokens", type=int, default=3072)
    ap.add_argument("--meta-model", default="headless/claude", help="orchestrator (Opus); '' to disable")
    ap.add_argument("--meta-interval", type=int, default=5)
    ap.add_argument("--watch", action="store_true", help="keep retrying until every mode reaches target")
    ap.add_argument("--sleep", type=int, default=1800, help="seconds between retries in --watch mode")
    args = ap.parse_args()

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]

    def all_done() -> bool:
        return all(gens_done(m) >= args.target for m in modes)

    print("=== resume ===")
    for m in modes:
        print(f"  {m}: {gens_done(m)}/{args.target} generations done")

    while True:
        stalled = []
        for m in modes:
            before, after = resume_mode(m, args.target, args.model, args.effort, args.max_tokens,
                                        args.meta_model, args.meta_interval)
            if after < args.target and after == before:
                stalled.append(m)

        if all_done():
            print("\nAll modes reached target. Next: score the champions "
                  "(harness/score_champion.py on runs/<mode>/best/main.py).")
            return
        if not args.watch:
            if stalled:
                print(f"\nStopped — likely hit the subscription limit on: {', '.join(stalled)}. "
                      f"Re-run `python resume.py` when your sub resets; progress is saved.")
            return
        print(f"\n[watch] sleeping {args.sleep}s before the next resume attempt "
              f"(Ctrl-C to stop; progress is saved) ...")
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
