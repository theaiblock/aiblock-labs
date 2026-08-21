#!/usr/bin/env python3
"""Interactive explorer for completed momentum-research runs."""

from __future__ import annotations

import json
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
RUNS_ROOT = ROOT / "runs"
MAX_COMPARISON_RUNS = 5
LOW_SAMPLE_TRADES = 30


def completed_runs(runs_root: Path = RUNS_ROOT) -> list[Path]:
    return sorted(
        path.parent.parent
        for path in runs_root.glob("*/artifacts/equity.csv")
        if (path.parent / "metrics.csv").exists()
        and (path.parent.parent / "config.json").exists()
    )


@st.cache_data(show_spinner=False)
def load_run(run_path: str) -> dict:
    run = Path(run_path)
    artifacts = run / "artifacts"
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(artifacts / "metrics.csv").iloc[0].to_dict()
    equity = pd.read_csv(artifacts / "equity.csv", parse_dates=["timestamp"])
    trades_path = artifacts / "trades.csv"
    trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
    validation_path = artifacts / "validation.json"
    validation = (
        json.loads(validation_path.read_text(encoding="utf-8"))
        if validation_path.exists()
        else {}
    )
    return {
        "name": run.name,
        "path": str(run),
        "config": config,
        "metrics": metrics,
        "equity": equity,
        "trades": trades,
        "validation": validation,
    }


def optional_number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def summary_row(run: dict) -> dict:
    metrics = run["metrics"]
    validation = run["validation"]
    mc = validation.get("monte_carlo", {})
    bootstrap = validation.get("bootstrap", {})
    walk_forward = validation.get("walk_forward", {})
    return {
        "Strategy": run["name"],
        "Interval": run["config"].get("interval", "—"),
        "Return": optional_number(metrics.get("total_return")),
        "Sharpe": optional_number(metrics.get("sharpe")),
        "Max drawdown": optional_number(metrics.get("max_drawdown")),
        "Trades": int(optional_number(metrics.get("trade_count", 0))),
        "MC Sharpe p": optional_number(mc.get("p_value_sharpe")),
        "Bootstrap P(Sharpe > 0)": optional_number(bootstrap.get("prob_positive")),
        "WF consistency": optional_number(walk_forward.get("consistency_rate")),
    }


def equity_comparison(selected: list[dict]) -> alt.Chart:
    frames = []
    for run in selected:
        frame = run["equity"][["timestamp", "equity"]].copy()
        frame["Equity index"] = frame["equity"] / frame["equity"].iloc[0] * 100
        frame["Strategy"] = run["name"]
        frames.append(frame[["timestamp", "Equity index", "Strategy"]])
    data = pd.concat(frames, ignore_index=True)
    return (
        alt.Chart(data)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("Equity index:Q", scale=alt.Scale(zero=False)),
            color=alt.Color("Strategy:N"),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Date"),
                "Strategy:N",
                alt.Tooltip("Equity index:Q", format=".2f"),
            ],
        )
        .properties(height=430)
        .interactive()
    )


def detail_equity_chart(run: dict) -> alt.Chart:
    frame = run["equity"].copy()
    frame["Strategy"] = frame["equity"] / frame["equity"].iloc[0] * 100
    if "benchmark_equity" in frame:
        frame["Buy and hold"] = frame["benchmark_equity"] / frame["benchmark_equity"].iloc[0] * 100
    columns = [column for column in ["Strategy", "Buy and hold"] if column in frame]
    data = frame.melt("timestamp", value_vars=columns, var_name="Series", value_name="Equity index")
    return (
        alt.Chart(data)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("Equity index:Q", scale=alt.Scale(zero=False)),
            color="Series:N",
            tooltip=[alt.Tooltip("timestamp:T", title="Date"), "Series:N", alt.Tooltip("Equity index:Q", format=".2f")],
        )
        .properties(height=350)
        .interactive()
    )


def drawdown_chart(run: dict) -> alt.Chart:
    frame = run["equity"][["timestamp", "drawdown"]].copy()
    frame["Drawdown"] = frame["drawdown"]
    return (
        alt.Chart(frame)
        .mark_area(color="#e45756", opacity=0.65)
        .encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y("Drawdown:Q", axis=alt.Axis(format="%")),
            tooltip=[alt.Tooltip("timestamp:T", title="Date"), alt.Tooltip("Drawdown:Q", format=".2%")],
        )
        .properties(height=230)
        .interactive()
    )


def monte_carlo_chart(run: dict, simulations: int = 1000, seed: int = 42) -> alt.Chart | None:
    trades = run["trades"]
    if trades.empty or "pnl" not in trades:
        return None
    pnls = trades.loc[trades["pnl"] != 0, "pnl"].astype(float).to_numpy()
    if not len(pnls):
        return None
    initial = float(run["config"].get("initial_cash", 1_000_000))
    rng = np.random.default_rng(seed)
    paths = np.vstack([initial + np.cumsum(rng.permutation(pnls)) for _ in range(simulations)])
    percentiles = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    data = pd.DataFrame(
        {
            "Trade": np.arange(1, len(pnls) + 1),
            "p05": percentiles[0],
            "p25": percentiles[1],
            "Median": percentiles[2],
            "p75": percentiles[3],
            "p95": percentiles[4],
            "Actual": initial + np.cumsum(pnls),
        }
    )
    outer = alt.Chart(data).mark_area(opacity=0.16).encode(x="Trade:Q", y="p05:Q", y2="p95:Q")
    inner = alt.Chart(data).mark_area(opacity=0.28).encode(x="Trade:Q", y="p25:Q", y2="p75:Q")
    lines = (
        alt.Chart(data.melt("Trade", value_vars=["Median", "Actual"], var_name="Series", value_name="Equity"))
        .mark_line(point=True)
        .encode(x="Trade:Q", y=alt.Y("Equity:Q", scale=alt.Scale(zero=False)), color="Series:N", tooltip=["Trade:Q", "Series:N", alt.Tooltip("Equity:Q", format=",.0f")])
    )
    return (outer + inner + lines).properties(height=330).interactive()


def walk_forward_chart(run: dict) -> alt.Chart | None:
    windows = run["validation"].get("walk_forward", {}).get("windows", [])
    if not windows:
        return None
    data = pd.DataFrame(windows)
    data["Return"] = data["return"]
    data["Window"] = data["window"].astype(str)
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("Window:N", sort=None),
            y=alt.Y("Return:Q", axis=alt.Axis(format="%")),
            color=alt.condition(alt.datum.Return >= 0, alt.value("#54a24b"), alt.value("#e45756")),
            tooltip=["Window:N", "start:N", "end:N", alt.Tooltip("Return:Q", format=".2%"), "trades:Q"],
        )
        .properties(height=330)
    )


st.set_page_config(page_title="Momentum Research Explorer", page_icon="📈", layout="wide")
st.title("Momentum Research Explorer")
st.caption("Completed Vibe-Trading experiments · offline research, not trading advice")

paths = completed_runs()
if not paths:
    st.info("No completed runs found under `runs/` yet.")
    st.stop()

runs = [load_run(str(path)) for path in paths]
summary = pd.DataFrame(summary_row(run) for run in runs).sort_values("Sharpe", ascending=False)

st.subheader("Experiment leaderboard")
st.caption("Sorted by Sharpe by default. High returns with very few trades are weak evidence.")
st.dataframe(
    summary,
    hide_index=True,
    width="stretch",
    column_config={
        "Return": st.column_config.NumberColumn(format="percent"),
        "Sharpe": st.column_config.NumberColumn(format="%.3f"),
        "Max drawdown": st.column_config.NumberColumn(format="percent"),
        "MC Sharpe p": st.column_config.NumberColumn(format="%.3f"),
        "Bootstrap P(Sharpe > 0)": st.column_config.NumberColumn(format="percent"),
        "WF consistency": st.column_config.NumberColumn(format="percent"),
    },
)

st.subheader("Compare equity curves")
default_names = summary["Strategy"].head(min(3, len(summary))).tolist()
selected_names = st.multiselect(
    f"Choose up to {MAX_COMPARISON_RUNS} strategies",
    summary["Strategy"].tolist(),
    default=default_names,
    max_selections=MAX_COMPARISON_RUNS,
)
if selected_names:
    selected = [run for run in runs if run["name"] in selected_names]
    st.altair_chart(equity_comparison(selected), width="stretch")
else:
    st.info("Select at least one strategy to compare.")

st.subheader("Strategy details")
detail_name = st.selectbox("Inspect one strategy", summary["Strategy"].tolist())
detail = next(run for run in runs if run["name"] == detail_name)
row = summary.loc[summary["Strategy"] == detail_name].iloc[0]

if row["Trades"] < LOW_SAMPLE_TRADES:
    st.warning(
        f"Low sample: only {int(row['Trades'])} completed trades. Monte Carlo and performance metrics "
        "are unstable and should not be treated as evidence of a durable edge."
    )

metric_columns = st.columns(5)
metric_columns[0].metric("Return", f"{row['Return']:.2%}")
metric_columns[1].metric("Sharpe", f"{row['Sharpe']:.3f}")
metric_columns[2].metric("Max drawdown", f"{row['Max drawdown']:.2%}")
metric_columns[3].metric("Trades", f"{int(row['Trades'])}")
metric_columns[4].metric("WF consistency", f"{row['WF consistency']:.0%}")

equity_tab, validation_tab, assumptions_tab, artifacts_tab = st.tabs(
    ["Equity & drawdown", "Validation", "Assumptions", "Artifacts"]
)
with equity_tab:
    st.altair_chart(detail_equity_chart(detail), width="stretch")
    st.altair_chart(drawdown_chart(detail), width="stretch")
with validation_tab:
    left, right = st.columns(2)
    with left:
        st.markdown("#### Trade-order Monte Carlo")
        mc_chart = monte_carlo_chart(detail)
        if mc_chart is None:
            st.info("No closed-trade P&L data available.")
        else:
            st.altair_chart(mc_chart, width="stretch")
        st.caption("The fan permutes realized trade P&Ls. It does not test parameter-selection overfitting.")
    with right:
        st.markdown("#### Walk-forward windows")
        wf_chart = walk_forward_chart(detail)
        if wf_chart is None:
            st.info("No walk-forward artifact available.")
        else:
            st.altair_chart(wf_chart, width="stretch")
    st.json(detail["validation"], expanded=False)
with assumptions_tab:
    st.markdown("#### Research assumptions")
    st.json(detail["config"].get("research_assumptions", {}), expanded=True)
    st.markdown("#### Full configuration")
    st.json(detail["config"], expanded=False)
with artifacts_tab:
    st.code(detail["path"])
    artifact_rows = []
    for artifact in sorted((Path(detail["path"]) / "artifacts").glob("*")):
        artifact_rows.append({"File": artifact.name, "Size (bytes)": artifact.stat().st_size})
    st.dataframe(pd.DataFrame(artifact_rows), hide_index=True, width="stretch")
    if not detail["trades"].empty:
        st.markdown("#### Trades")
        st.dataframe(detail["trades"], hide_index=True, width="stretch")
