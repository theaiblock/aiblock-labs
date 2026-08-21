# Momentum Research Loop

A lightweight, stateful agent harness built on Vibe-Trading. Each invocation starts a fresh coding agent. The agent reads the user's mandate, prior experiments, and user feedback; chooses one untested momentum hypothesis; runs a backtest and Monte Carlo validation; then appends what happened to the journal.

The durable interface is four Markdown files:

- `MANDATE.md` — the user's objective and non-negotiable research constraints.
- `JOURNAL.md` — append-only machine memory of every attempted experiment.
- `FEEDBACK.md` — user steering, read before every new experiment.
- `PROMPT.md` — operating contract for each fresh agent.

`loop.sh` only launches agents; it does not decide what to test.

## Run

```bash
./loop.sh --opencode 1
./loop.sh --claude 1
./loop.sh --codex 1
MODEL_OVERRIDE=<model> ./loop.sh --opencode 5
```

Each runner has a public default model (`claude-opus-5` for `--claude`,
`anthropic/claude-opus-5` for `--opencode`, the CLI's own default for `--codex`).
Override one runner with `CLAUDE_MODEL`, `OPENCODE_MODEL` or `CODEX_MODEL`, or all
of them at once with `MODEL_OVERRIDE`.

Create a supported environment and install the pinned dependency:

```bash
python3.13 -m venv .venv   # any of 3.11 / 3.12 / 3.13
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Vibe-Trading is installed as `vibe-trading-ai==0.1.12`; no source checkout or `VIBE_TRADING_ROOT` is required. Python 3.14 is outside Vibe-Trading's supported range.

## Research explorer

After one or more completed experiments, start the local dashboard from this
directory:

```bash
.venv/bin/streamlit run app.py
```

Open the URL printed by Streamlit, normally `http://localhost:8501`. The app
discovers completed directories under `runs/` automatically, so new agent runs
appear after refreshing the page; agents do not need to generate charts.

The explorer provides:

- A sortable, robustness-first leaderboard. It defaults to Sharpe rather than
  headline return.
- A multi-select equity comparison capped at five visible strategies, keeping
  the chart legible as the experiment count grows.
- A focused strategy view with equity versus buy-and-hold, drawdown, trade-order
  Monte Carlo, walk-forward windows, configuration, assumptions, artifacts, and
  the trade ledger.
- A visible low-sample warning for strategies with fewer than 30 completed
  trades.

The app is read-only: it does not alter run artifacts, the journal, or strategy
rankings. Its Monte Carlo fan permutes the observed closed-trade P&Ls and is
explicitly presented as path evidence, not proof against parameter overfitting.

## What is not in this repository

Three things are generated rather than committed, so a clone stays small and
reproducible:

- `runs/*/artifacts/ohlcv_*.csv` — the raw price data each backtest fetched. The
  explorer never reads it, so the dashboard works on a fresh clone; re-running a
  backtest re-downloads it.
- `reports/` and `logs/` — rendered comparison charts and per-iteration agent
  logs, both regenerated on the next run.
- `runs/*/*.sandbox-attempt.log` — the first, failed attempt at each run, when
  the sandbox had no DNS. `JOURNAL.md` refers to these because the harness
  records blockers as well as results; they are kept locally with the run and
  contain nothing but resolver errors.
