from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path


FORBIDDEN_CALLS = {"compile", "eval", "exec", "globals", "input", "locals", "open", "__import__"}


def _validate_source(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Candidate imports are not allowed")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            raise ValueError(f"Candidate call is not allowed: {node.func.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Candidate dunder access is not allowed")


def _load_candidate(path: Path):
    _validate_source(path)
    name = f"candidate_{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}_{id(path)}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load candidate")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "allocate", None)):
        raise ValueError("candidate.py must define allocate(history)")
    return module.allocate


def _read_prices(path: Path) -> tuple[list[str], dict[str, list[float]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No prices in {path}")
    assets = [name for name in rows[0] if name != "date"]
    return [row["date"] for row in rows], {
        asset: [float(row[asset]) for row in rows] for asset in assets
    }


def _returns(prices: list[float]) -> list[float]:
    return [prices[index] / prices[index - 1] - 1.0 for index in range(1, len(prices))]


def _weights(raw: object, assets: list[str]) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(assets):
        raise ValueError("allocate() must return exactly one weight for every asset")
    weights = {asset: float(raw[asset]) for asset in assets}
    if any(not math.isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("Weights must be finite and non-negative")
    if not math.isclose(sum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-8):
        raise ValueError("Weights must sum to one")
    return weights


def _score(candidate_path: Path, sealed_dir: Path) -> dict:
    config = json.loads((sealed_dir / "manifest.json").read_text(encoding="utf-8"))["evaluation"]
    _, train_prices = _read_prices(sealed_dir.parent / "train" / "prices.csv")
    dates, holdout_prices = _read_prices(sealed_dir / "holdout_prices.csv")
    assets = sorted(train_prices)
    if assets != sorted(holdout_prices):
        raise ValueError("Train and hold-out assets differ")

    all_prices = {asset: train_prices[asset] + holdout_prices[asset] for asset in assets}
    all_returns = {asset: _returns(values) for asset, values in all_prices.items()}
    train_return_count = len(next(iter(train_prices.values()))) - 1
    lookback = int(config["lookback_days"])
    rebalance = int(config["rebalance_days"])
    fee = float(config["taker_bps"]) / 10_000
    allocate = _load_candidate(candidate_path)

    portfolio_returns: list[float] = []
    turnovers: list[float] = []
    previous = {asset: 0.0 for asset in assets}
    rebalance_dates: list[str] = []
    # Concatenating train and hold-out creates one scored return for every hold-out
    # price row, including the boundary return from the final training close.
    holdout_return_count = len(next(iter(holdout_prices.values())))
    for offset in range(0, holdout_return_count, rebalance):
        end = train_return_count + offset
        history = {asset: all_returns[asset][max(0, end - lookback):end] for asset in assets}
        weights = _weights(allocate(history), assets)
        turnover = 1.0 if not turnovers else sum(abs(weights[a] - previous[a]) for a in assets) / 2
        turnovers.append(turnover)
        previous = weights
        rebalance_dates.append(dates[offset])

        stop = min(offset + rebalance, holdout_return_count)
        for local_index in range(offset, stop):
            global_index = train_return_count + local_index
            daily = sum(weights[asset] * all_returns[asset][global_index] for asset in assets)
            if local_index == offset:
                daily -= fee * turnover
            portfolio_returns.append(daily)

    n = len(portfolio_returns)
    mean = sum(portfolio_returns) / n
    variance = sum((value - mean) ** 2 for value in portfolio_returns) / (n - 1)
    volatility = math.sqrt(variance) * math.sqrt(365)
    annual_return = mean * 365
    equity = peak = 1.0
    max_drawdown = 0.0
    for value in portfolio_returns:
        equity *= 1 + value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)

    return {
        "annual_return": round(annual_return, 6),
        "annual_volatility": round(volatility, 6),
        "max_drawdown": round(max_drawdown, 6),
        "mean_turnover": round(sum(turnovers) / len(turnovers), 6),
        "observations": n,
        "rebalances": len(turnovers),
        "sharpe": round(annual_return / volatility, 6) if volatility else None,
        "start": rebalance_dates[0],
        "end": dates[-1],
    }


def evaluate(candidate_path: Path, sealed_dir: Path) -> dict:
    first = _score(candidate_path, sealed_dir)
    second = _score(candidate_path, sealed_dir)
    if first != second:
        raise RuntimeError("Candidate evaluation is not deterministic")
    return first
