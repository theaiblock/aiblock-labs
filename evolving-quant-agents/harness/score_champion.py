#!/usr/bin/env python3
"""Open the sealed test set — ONCE — on a champion program, and print the honest scorecard.

This is the ritual the whole experiment is built around: during evolution the search never sees the
test window; here we run any program (the seed, Champion-Naive, Champion-Honest) across ALL
three windows with real 10 bps costs and report in-sample vs out-of-sample. The naive champion
is ALSO scored on its own no-cost in-sample window so we can show the beautiful number it was
evolved to produce next to what it actually does out-of-sample.

Usage:
    python score_champion.py --program runs/naive/best/main.py  --label Champion-Naive  --naive
    python score_champion.py --program runs/honest/best/main.py --label Champion-Honest
    python score_champion.py --program harness/initial.py       --label Seed
Add --json to also dump the metrics dict.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import (  # noqa: E402
    FEE_BPS, WINDOWS, load_panel, load_signal, run_backtest,
)


def _row(name: str, m: dict) -> str:
    return (f"  {name:<12} Sharpe={_f(m.get('sharpe')):>7}  return={_pct(m.get('total_return')):>8}  "
            f"maxDD={_pct(m.get('max_drawdown')):>8}  turnover={_f(m.get('ann_turnover')):>6}  "
            f"in-mkt={_pct(m.get('pct_in_market')):>6}")


def _f(x) -> str:
    return f"{x:.3f}" if isinstance(x, (int, float)) else str(x)


def _pct(x) -> str:
    return f"{x*100:.1f}%" if isinstance(x, (int, float)) else str(x)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--program", required=True)
    ap.add_argument("--label", default="program")
    ap.add_argument("--naive", action="store_true",
                    help="also score the no-cost full-history in-sample window (the naive scoreboard)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    prog = str(Path(args.program).resolve())
    sig = load_signal(prog)
    panel = load_panel()

    out: dict = {"label": args.label, "program": prog, "fee_bps": FEE_BPS}
    print(f"\n=== {args.label} ===  ({prog})")

    if args.naive:
        ins = run_backtest(sig, panel, WINDOWS["naive_full"], fee_bps=0.0)
        out["naive_in_sample_0bps"] = ins
        print(_row("IN-SAMPLE*", ins) + "   [full history, 0 costs — the scoreboard it was evolved on]")

    for w in ("train", "val", "test"):
        m = run_backtest(sig, panel, WINDOWS[w], fee_bps=FEE_BPS)
        out[w] = m
        tag = " <-- SEALED OOS" if w == "test" else ""
        print(_row(w.upper(), m) + f"   [{FEE_BPS:.0f}bps costs]{tag}")

    if args.json:
        print("\n" + json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
