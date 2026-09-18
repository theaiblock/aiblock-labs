Implement the trading signal described in `thesis.json` as `signal(close, volume, universe)` in
`candidate.py`.

- Follow `contract.md`. The data and the engine are fixed; you only write the signal.
- Implement the thesis exactly as written. Do not improve, tune or change the idea. Where the
  rule is ambiguous, choose the most literal reading and say which choice you made in `notes`.
- Run `./check` after every change and keep fixing until it prints PASS. It reports whether the
  code is valid (imports, output shape, weights 0 outside the universe and summing to at most 1, no
  look-ahead, runs in the engine). It does not report performance.
- `engine.load()` returns the data (`.close`, `.volume`, `.universe`) if you want to inspect it.

When `./check` prints PASS, reply with status `done`. If the thesis cannot be implemented within
the contract, reply with status `blocked` and the reason.
