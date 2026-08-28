from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path


EVALUATOR = Path(__file__).parents[1] / "tasks" / "crypto_allocation" / "evaluate.py"


def load_evaluator():
    import importlib.util
    spec = importlib.util.spec_from_file_location("crypto_evaluator_test", EVALUATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class CryptoEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.task = Path(self.temp.name)
        (self.task / "train").mkdir()
        (self.task / "sealed").mkdir()
        self._prices(self.task / "train" / "prices.csv", 1, 8)
        self._prices(self.task / "sealed" / "holdout_prices.csv", 8, 14)
        (self.task / "sealed" / "manifest.json").write_text(json.dumps({
            "evaluation": {"lookback_days": 3, "rebalance_days": 2, "taker_bps": 10}
        }))

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _prices(path: Path, start: int, stop: int) -> None:
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("date", "AAA", "BBB"))
            for day in range(start, stop):
                writer.writerow((f"2024-01-{day:02d}", 100 + day, 100 - day / 2))

    def test_equal_weight_is_scored_deterministically(self) -> None:
        candidate = self.task / "candidate.py"
        candidate.write_text(
            "def allocate(history):\n"
            "    return {name: 1 / len(history) for name in history}\n"
        )
        metrics = load_evaluator().evaluate(candidate, self.task / "sealed")
        self.assertEqual(6, metrics["observations"])
        self.assertEqual(3, metrics["rebalances"])
        self.assertEqual("2024-01-08", metrics["start"])

    def test_candidate_cannot_import_or_read_files(self) -> None:
        candidate = self.task / "candidate.py"
        candidate.write_text("import os\ndef allocate(history):\n    return {}\n")
        with self.assertRaisesRegex(ValueError, "imports are not allowed"):
            load_evaluator().evaluate(candidate, self.task / "sealed")

    def test_invalid_weights_are_rejected(self) -> None:
        candidate = self.task / "candidate.py"
        candidate.write_text("def allocate(history):\n    return {'AAA': 1.0, 'BBB': 1.0}\n")
        with self.assertRaisesRegex(ValueError, "sum to one"):
            load_evaluator().evaluate(candidate, self.task / "sealed")


if __name__ == "__main__":
    unittest.main()
