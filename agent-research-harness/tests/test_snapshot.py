from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path


TASK = Path(__file__).parents[1] / "tasks" / "crypto_allocation"


class SnapshotTests(unittest.TestCase):
    def test_snapshot_hashes_and_split_are_pinned(self) -> None:
        manifest = json.loads((TASK / "sealed" / "manifest.json").read_text())
        train = TASK / "train" / "prices.csv"
        holdout = TASK / "sealed" / "holdout_prices.csv"
        self.assertEqual(manifest["train_sha256"], hashlib.sha256(train.read_bytes()).hexdigest())
        self.assertEqual(manifest["holdout_sha256"], hashlib.sha256(holdout.read_bytes()).hexdigest())

        with train.open(newline="") as handle:
            train_rows = list(csv.DictReader(handle))
        with holdout.open(newline="") as handle:
            holdout_rows = list(csv.DictReader(handle))
        self.assertEqual(manifest["train_rows"], len(train_rows))
        self.assertEqual(manifest["holdout_rows"], len(holdout_rows))
        self.assertLess(train_rows[-1]["date"], manifest["split"])
        self.assertGreaterEqual(holdout_rows[0]["date"], manifest["split"])
        self.assertEqual(set(manifest["symbols"]), set(train_rows[0]) - {"date"})


if __name__ == "__main__":
    unittest.main()
