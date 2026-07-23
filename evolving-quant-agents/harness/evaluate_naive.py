"""NAIVE evaluator — the overfitting scoreboard (the foil).

combined_score = in-sample Sharpe over the WHOLE history, ZERO transaction costs, NO split.
This is exactly what quantevolve does. The evolved strategy is fit and scored on the same
bars, so the search is free to curve-fit. We show what that produces, then run the champion
on the sealed test set to watch it collapse.

Contract (matches the ShinkaEvolve example): CLI --program_path --results_dir, writes
metrics.json {combined_score, public, private} + correct.json {correct, error}.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import (  # noqa: E402
    WINDOWS, combined_score_from, load_panel, load_signal, run_backtest,
)


def _write(results_dir: str, metrics: dict, correct: bool, error: str) -> None:
    rp = Path(results_dir)
    rp.mkdir(parents=True, exist_ok=True)
    (rp / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (rp / "correct.json").write_text(json.dumps({"correct": correct, "error": error}, indent=2), encoding="utf-8")


def _fail(msg: str) -> dict:
    return {"combined_score": -10.0, "public": {"score": -10.0, "error": msg}, "private": {"error": msg}}


def main(program_path: str, results_dir: str) -> None:
    try:
        sig = load_signal(program_path)
        panel = load_panel()
        m = run_backtest(sig, panel, WINDOWS["naive_full"], fee_bps=0.0)  # no costs, full window
        score = combined_score_from(m)
        metrics = {
            "combined_score": score,
            "public": {"score": score, "sharpe_in_sample": m.get("sharpe"),
                       "total_return": m.get("total_return"), "max_drawdown": m.get("max_drawdown"),
                       "ann_turnover": m.get("ann_turnover"), "pct_in_market": m.get("pct_in_market")},
            "private": {"window": "naive_full", "fee_bps": 0.0, "n_days": m.get("n_days")},
        }
        print(f"[naive] in-sample Sharpe={m.get('sharpe')} return={m.get('total_return')} "
              f"maxDD={m.get('max_drawdown')} -> combined_score={score}")
        _write(results_dir, metrics, correct=True, error="")
    except Exception as e:  # noqa: BLE001
        metrics = _fail(str(e))
        print(f"[naive] FAIL: {e}", file=sys.stderr)
        _write(results_dir, metrics, correct=False, error=str(e))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program_path", required=True)
    ap.add_argument("--results_dir", required=True)
    a = ap.parse_args()
    main(a.program_path, a.results_dir)
