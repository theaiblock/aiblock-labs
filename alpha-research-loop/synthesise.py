"""Synthesis: one model call reads the analysis of a population and writes its conclusions.

The model sees the research prompt, the contract and analysis/analysis.md, nothing else: no code, no
single backtest. Every number it cites is checked against analysis.md; unmatched numbers go back to
the model once, and anything still unmatched is recorded in the output rather than dropped.

    python synthesise.py populations/broad                     # Claude Opus 5
    python synthesise.py populations/broad --runner codex

The synthesis also writes `next_prompt`, the research prompt for the next round. Saved as
synthesis/next_prompt-<run>.md, it can be fed straight back into ideate.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ideate import DEFAULT_MODEL, RUNNERS, validate

ROOT = Path(__file__).parent
SCHEMA = ROOT / "synthesise" / "synthesis.schema.json"
NUMBER = re.compile(r"\d+/\d+|\d+(?:\.\d+)?%?")


def numbers(text: str) -> set[str]:
    return set(NUMBER.findall(text.replace(",", "")))


def unmatched(obj: dict, source: set[str]) -> list[str]:
    cited = set()
    for f in obj["findings"]:
        cited |= numbers(f["claim"] + " " + f["evidence"])
    for fam in obj["families"]:
        cited |= numbers(fam["verdict_note"]) | {f"{fam['sharpe']:.2f}"}
    cited |= numbers(obj["headline"] + obj["model_comparison"] + obj["regime_dependence"])
    # label digits (CLD_03) and bare small integers used as counts in prose are not claims
    cited = {c for c in cited if not re.fullmatch(r"\d", c)}
    return sorted(c for c in cited if c not in source)


def render(obj: dict, meta: dict) -> str:
    L = [f"# Synthesis — {meta['idea_id']}", "", f"_{meta['model']} · {meta['generated_at']}_", "",
         f"**{obj['headline']}**", "", "## Findings", ""]
    L += [f"- **{f['claim']}** ({f['strength']}) — {f['evidence']}" for f in obj["findings"]]
    L += ["", "## Families", "", "| family | ideas | Sharpe | what it changes | vs benchmark |", "|---|---|---|---|---|"]
    L += [f"| {f['name']} | {', '.join(f['labels'])} | {f['sharpe']:.2f} | {f['mechanism']} | **{f['verdict']}** — {f['verdict_note']} |"
          for f in obj["families"]]
    L += ["", "## Model comparison", "", obj["model_comparison"], "", "## Regime dependence", "",
          obj["regime_dependence"], "", "## Caveats", ""]
    L += [f"- {c}" for c in obj["caveats"]]
    L += ["", "## Next experiments", ""]
    L += [f"{k}. **{e['experiment']}** — {e['reason']}" for k, e in enumerate(obj["next_experiments"], 1)]
    L += ["", "## Next research prompt", "", obj["next_prompt"]]
    if meta["unmatched_numbers"]:
        L += ["", f"⚠️ Numbers not found in analysis.md: {', '.join(meta['unmatched_numbers'])}"]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("idea_dir", type=Path)
    ap.add_argument("--runner", choices=RUNNERS, default="claude")
    ap.add_argument("--model")
    ap.add_argument("--idea", type=Path, help="research prompt file (default: ideas/<idea_dir name>.md)")
    args = ap.parse_args()
    model = args.model or DEFAULT_MODEL[args.runner]
    idea_id = args.idea_dir.name
    analysis = (args.idea_dir / "analysis" / "analysis.md").read_text()
    prompt = ((ROOT / "synthesise" / "prompt.md").read_text()
              .replace("{idea}", (args.idea or ROOT / "ideas" / f"{idea_id}.md").read_text().strip())
              .replace("{contract}", (ROOT / "contract.md").read_text().strip())
              .replace("{analysis}", analysis.strip()))
    schema = json.loads(SCHEMA.read_text())
    source = numbers(analysis)

    ask, cost, rounds = prompt, 0.0, 0
    for rounds in (1, 2):
        with tempfile.TemporaryDirectory() as cwd:
            obj, used, c = RUNNERS[args.runner](ask, model, cwd, SCHEMA)
        cost += c or 0.0
        validate(obj, schema, "synthesis")
        missing = unmatched(obj, source)
        if not missing:
            break
        ask = (prompt + "\n\nYour previous answer cited numbers that do not appear in the analysis: "
               + ", ".join(missing) + ". Use only numbers copied exactly from the analysis, or remove them.")

    out = args.idea_dir / "synthesis"
    out.mkdir(exist_ok=True)
    stamp = datetime.now(UTC)
    run_id = f"synthesis-{args.runner}-{stamp:%Y%m%dT%H%M%SZ}"
    meta = {"run_id": run_id, "idea_id": idea_id, "runner": args.runner, "model": used, "rounds": rounds,
            "unmatched_numbers": missing, "cost_usd": round(cost, 4) if args.runner == "claude" else None,
            "analysis_sha256": hashlib.sha256(analysis.encode()).hexdigest(),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "generated_at": stamp.isoformat(timespec="seconds")}
    (out / f"{run_id}.json").write_text(json.dumps({**meta, "synthesis": obj}, indent=2) + "\n")
    (out / f"{run_id}.md").write_text(render(obj, meta))
    (out / f"next_prompt-{run_id}.md").write_text(obj["next_prompt"].strip() + "\n")
    print((out / f"{run_id}.md").read_text())
    print(f"{run_id}: {rounds} round(s), cost {meta['cost_usd']}, unmatched {missing or 'none'}")


if __name__ == "__main__":
    main()
