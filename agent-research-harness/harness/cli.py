from __future__ import annotations

import argparse
import json
from pathlib import Path

from .host import Harness


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage and score sealed agent research runs")
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage")
    stage.add_argument("task")
    submit = sub.add_parser("submit")
    submit.add_argument("workspace", type=Path)
    args = parser.parse_args()

    harness = Harness(Path.cwd())
    if args.command == "stage":
        print(harness.stage(args.task))
        return

    result = harness.submit(args.workspace)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
