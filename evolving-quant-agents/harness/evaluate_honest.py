"""HONEST evaluator — the disciplined scoreboard.

combined_score = VALIDATION Sharpe AFTER real transaction costs (10 bps/side), on a strict
train/validation/sealed-test split. The search may climb validation; it never sees the test
set (that is opened once, on the final champion, by score_champion.py). Train metrics are
reported for context only — train is not the sealed test, so exposing it does not leak.

Contract: CLI --program_path --results_dir, writes metrics.json {combined_score, public,
private} + correct.json {correct, error}. Same engine as the naive evaluator; only the
window and the cost differ — that is the entire point of the experiment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backtest import (  # noqa: E402
    FEE_BPS, WINDOWS, combined_score_from, load_panel, load_signal, run_backtest,
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
        val = run_backtest(sig, panel, WINDOWS["val"], fee_bps=FEE_BPS)
        train = run_backtest(sig, panel, WINDOWS["train"], fee_bps=FEE_BPS)  # context only
        score = combined_score_from(val)  # fitness = VALIDATION Sharpe after costs
        metrics = {
            "combined_score": score,
            "public": {"score": score, "val_sharpe": val.get("sharpe"),
                       "val_return": val.get("total_return"), "val_max_drawdown": val.get("max_drawdown"),
                       "train_sharpe": train.get("sharpe"), "ann_turnover": val.get("ann_turnover"),
                       "pct_in_market": val.get("pct_in_market")},
            "private": {"window": "val", "fee_bps": FEE_BPS, "val_n_days": val.get("n_days")},
        }
        print(f"[honest] val Sharpe(after {FEE_BPS}bps)={val.get('sharpe')} "
              f"train Sharpe={train.get('sharpe')} -> combined_score={score}")
        _write(results_dir, metrics, correct=True, error="")
    except Exception as e:  # noqa: BLE001
        metrics = _fail(str(e))
        print(f"[honest] FAIL: {e}", file=sys.stderr)
        _write(results_dir, metrics, correct=False, error=str(e))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--program_path", required=True)
    ap.add_argument("--results_dir", required=True)
    a = ap.parse_args()
    main(a.program_path, a.results_dir)
