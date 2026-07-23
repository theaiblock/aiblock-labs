#!/usr/bin/env python3
"""Run ShinkaEvolve on the trading seed against ONE of the two evaluators.

Same loop, same seed, same data — only the evaluator (scoreboard) changes:
    python run_evolve.py --mode naive  --generations 2   # overfitting scoreboard
    python run_evolve.py --mode honest --generations 2   # disciplined scoreboard (val, 10bps)

Backend = headless/claude, which runs on a Claude subscription with no API key (see
RUNNING_SHINKA.md). Outputs land in runs/<mode>/ (gitignored). The evolved champion and
its sealed-test score are the keepers.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from shinka.core import EvolutionConfig, ShinkaEvolveRunner
from shinka.database import DatabaseConfig
from shinka.launch import LocalJobConfig

TASK_DIR = Path(__file__).resolve().parent
HARNESS = TASK_DIR / "harness"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["naive", "honest"], required=True)
    ap.add_argument("--generations", type=int, default=12)
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--patch-types", default="diff,full", help="comma list: diff,full")
    ap.add_argument("--results-dir", default=None)
    # Cost knobs — Sonnet + low effort + small max_tokens ~= 5-10x less subscription usage
    # than the old Opus/high-effort defaults, plenty for mutating a small strategy function.
    ap.add_argument("--model", default="headless/claude@sonnet",
                    help="MUTATION model (writes code, ~1/gen). Sonnet is plenty + cheap.")
    ap.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh"])
    ap.add_argument("--max-tokens", type=int, default=3072)
    # Orchestrator: a smarter model reasons about the whole search every --meta-interval gens
    # (a handful of calls total). Opus here + Sonnet mutations = best-of-both, cheap. Non-fatal
    # if Opus is rate-limited (the meta step is just skipped). Pass --meta-model '' to disable.
    ap.add_argument("--meta-model", default="headless/claude",
                    help="META/orchestrator model (Opus). '' to disable.")
    ap.add_argument("--meta-interval", type=int, default=5)
    args = ap.parse_args()

    eval_program = HARNESS / (f"evaluate_{args.mode}.py")
    results_dir = args.results_dir or str(TASK_DIR / "runs" / args.mode)
    patch_types = [p.strip() for p in args.patch_types.split(",") if p.strip()]
    probs = [round(1.0 / len(patch_types), 4)] * len(patch_types)

    job_config = LocalJobConfig(eval_program_path=str(eval_program), time="00:05:00")
    db_config = DatabaseConfig(
        db_path=str(Path(results_dir) / "evolution_db.sqlite"),
        num_islands=2, archive_size=8, num_archive_inspirations=1, num_top_k_inspirations=1,
    )
    evo_config = EvolutionConfig(
        patch_types=patch_types,
        patch_type_probs=probs,
        num_generations=args.generations,
        max_patch_resamples=1,
        max_patch_attempts=2,   # cap the retry storm: <=2 calls/gen, not 6
        job_type="local",
        language="python",
        llm_models=[args.model],          # MUTATION (writes code) — cheap Sonnet
        llm_dynamic_selection="fixed",
        llm_kwargs={"temperatures": [0.0], "max_tokens": args.max_tokens, "reasoning_efforts": [args.effort]},
        meta_llm_models=([args.meta_model] if args.meta_model else None),   # ORCHESTRATOR — Opus, rare
        meta_rec_interval=args.meta_interval,
        meta_llm_kwargs=({"max_tokens": 4096, "reasoning_efforts": ["medium"]} if args.meta_model else {}),
        embedding_model=None,             # no API key needed for embeddings
        init_program_path=str(HARNESS / "initial.py"),
        results_dir=results_dir,
        max_novelty_attempts=1,
    )

    runner = ShinkaEvolveRunner(
        evo_config=evo_config, job_config=job_config, db_config=db_config,
        max_evaluation_jobs=args.concurrency, max_proposal_jobs=args.concurrency,
        max_db_workers=2, verbose=True,
    )
    print(f"[run] mode={args.mode} eval={eval_program.name} gens={args.generations} "
          f"mutate={args.model}({args.effort}) meta={args.meta_model or 'off'}@{args.meta_interval} "
          f"patches={patch_types} -> {results_dir}")
    runner.run()


if __name__ == "__main__":
    main()
