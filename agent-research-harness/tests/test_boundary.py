from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness.host import Harness


class BoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        task = self.root / "tasks" / "demo"
        (task / "train").mkdir(parents=True)
        (task / "sealed").mkdir()
        for name in ("MANDATE.md", "FEEDBACK.md", "JOURNAL.md", "PROMPT.md"):
            (task / name).write_text(name, encoding="utf-8")
        (task / "candidate.py").write_text("VALUE = 1\n", encoding="utf-8")
        (task / "train" / "visible.txt").write_text("train", encoding="utf-8")
        (task / "sealed" / "hidden.txt").write_text("holdout", encoding="utf-8")
        (task / "evaluate.py").write_text(
            "def evaluate(candidate_path, sealed_dir):\n"
            "    return {'score': (sealed_dir / 'hidden.txt').read_text()}\n",
            encoding="utf-8",
        )
        self.harness = Harness(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_stage_excludes_holdout_and_evaluator(self) -> None:
        workspace = self.harness.stage("demo")
        self.assertEqual("train", (workspace / "train" / "visible.txt").read_text())
        self.assertFalse((workspace / "sealed").exists())
        self.assertFalse((workspace / "evaluate.py").exists())

    def test_submit_scores_host_side_and_fingerprints_inputs(self) -> None:
        workspace = self.harness.stage("demo")
        (workspace / "proposal.json").write_text(
            json.dumps({
                "slug": "baseline",
                "hypothesis": "establish the baseline",
                "expected_direction": "neutral",
            }),
            encoding="utf-8",
        )
        result = self.harness.submit(workspace)
        self.assertEqual({"score": "holdout"}, result["metrics"])
        self.assertEqual(64, len(result["fingerprint"]))
        self.assertIn("train/visible.txt", result["inputs"])
        self.assertIn("sealed/hidden.txt", result["inputs"])
        journal = (self.root / "tasks" / "demo" / "JOURNAL.md").read_text()
        self.assertIn("establish the baseline", journal)
        self.assertIn(result["fingerprint"], journal)

        next_workspace = self.harness.stage("demo")
        self.assertIn("establish the baseline", (next_workspace / "JOURNAL.md").read_text())


if __name__ == "__main__":
    unittest.main()
