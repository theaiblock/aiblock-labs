"""Run by the implementing agent: ./check  -> PASS, or the list of errors to fix.

Reports validity only, never performance, so the agent implements the thesis instead of tuning it."""
import sys
from pathlib import Path

import engine

source = Path("candidate.py").read_text()
data = engine.load()
errors, w = engine.validate(source, data)
if not errors:
    try:
        engine.score(w, data)
    except Exception as exc:
        errors = [f"engine failed on this signal: {type(exc).__name__}: {exc}"]
if not errors and float(w.to_numpy().sum()) == 0.0:
    errors = ["signal is 0 for every coin on every day"]
if errors:
    print("FAIL")
    print("\n".join(f"- {e}" for e in errors))
    sys.exit(1)
print("PASS")
