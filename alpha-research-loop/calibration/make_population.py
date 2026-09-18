"""Write the hand-written variants as a population (populations/_calibration) so backtest.py and
analyse.py can be tested end to end without calling a model. Good variants are filed as runner
"claude", bad ones as "codex", only so the analysis has two groups to compare."""
import json
from pathlib import Path

from variants import VARIANTS

ROOT = Path(__file__).parents[1]
pop = ROOT / "populations" / "_calibration"
for d in ("ideas", "implementations"):
    (pop / d).mkdir(parents=True, exist_ok=True)
n = {"claude": 0, "codex": 0}
for name, src in VARIANTS.items():
    if name == "benchmark":
        continue
    runner = "claude" if name.startswith("good") else "codex"
    n[runner] += 1
    spec_id = f"_calibration-{runner}-hand-{n[runner]:03d}"
    thesis = {"title": name, "thesis": "hand-written calibration variant", "change_vs_benchmark": name,
              "signal_rule": "see implementation", "parameters": [], "warmup_days": 60,
              "expected_vs_benchmark": "beats" if runner == "claude" else "trails", "falsified_if": "-"}
    (pop / "ideas" / f"{spec_id}.json").write_text(json.dumps(
        {"spec_id": spec_id, "idea_id": "_calibration", "runner": runner, "model": "hand-written", "thesis": thesis}, indent=2))
    impl_id = f"{spec_id}.impl-A"
    (pop / "implementations" / f"{impl_id}.py").write_text(src.lstrip())
    (pop / "implementations" / f"{impl_id}.json").write_text(json.dumps(
        {"impl_id": impl_id, "spec_id": spec_id, "idea_id": "_calibration", "runner": runner,
         "model": "hand-written", "status": "ok"}, indent=2))
print(f"wrote {sum(n.values())} variants to {pop}")
