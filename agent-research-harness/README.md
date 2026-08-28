# agent-research-harness

A small host/agent boundary for reproducible autonomous research.

The host stages a disposable workspace containing only the task mandate, research memory,
training data, and candidate interface. A coding agent makes exactly one submission there. The
host copies that submission into an immutable run bundle and evaluates it with code and hold-out
data that were never placed in the agent workspace.

This starter intentionally contains no claimed portfolio result. Run real iterations and treat
their fingerprinted artifacts as the evidence.

## Commands

```bash
python -m harness.cli stage crypto_allocation
python -m harness.cli submit <workspace-path>
./loop.sh --codex 3
python -m unittest discover -s tests -v
```

Build the pinned first-task snapshot once with `python scripts/build_snapshot.py`. The generated
CSV files, dates, venue, symbols, raw hashes, split, and evaluation settings then become part of
the evidence fingerprint; normal research runs never fetch live data.

The default snapshot builder fetches eight Binance USDT spot markets. Training is 2021-01-01
through 2023-12-31; the sealed hold-out is 2024-01-01 through 2025-12-31. Market data is generated
locally and ignored by Git. The modest universe is intentional: this first task demonstrates the
agent/evaluator boundary rather than becoming another large optimizer sweep.

`stage` prints the disposable workspace path. After an agent writes `proposal.json` and
`candidate.py`, `submit` locks them into `runs/<run-id>/`, invokes the host-side evaluator, and
writes `result.json` with a content fingerprint.

`loop.sh` repeats that lifecycle with a fresh workspace and fresh model context each time. The
host appends the scored proposal and fingerprint to the task journal, so the next staged agent
inherits evidence without inheriting the previous conversation.

## Trust boundary

The agent workspace never receives:

- `tasks/<task>/sealed/`
- `tasks/<task>/evaluate.py`
- harness submission/evaluation internals

The CLI refuses submissions whose workspace contains reserved sealed/evaluator paths. For a real
autonomous run, invoke the model with its filesystem sandbox rooted at the printed workspace.
Process working-directory isolation alone is not a security boundary.
