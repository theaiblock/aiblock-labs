from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType


VISIBLE_FILES = ("MANDATE.md", "FEEDBACK.md", "JOURNAL.md", "PROMPT.md", "candidate.py")
REQUIRED_SUBMISSION = ("proposal.json", "candidate.py")
RESERVED_NAMES = {"sealed", "evaluate.py"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Harness:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.tasks = self.root / "tasks"
        self.runs = self.root / "runs"

    def stage(self, task_name: str) -> Path:
        task = (self.tasks / task_name).resolve()
        if task.parent != self.tasks.resolve() or not task.is_dir():
            raise ValueError(f"Unknown task: {task_name}")

        workspace = Path(tempfile.mkdtemp(prefix=f"agent-research-{task_name}-"))
        for name in VISIBLE_FILES:
            source = task / name
            if source.exists():
                shutil.copy2(source, workspace / name)
        shutil.copytree(task / "train", workspace / "train")
        (workspace / ".task.json").write_text(
            json.dumps({"task": task_name}, sort_keys=True) + "\n", encoding="utf-8"
        )
        return workspace

    def submit(self, workspace: Path) -> dict:
        workspace = workspace.resolve()
        task_name = json.loads((workspace / ".task.json").read_text(encoding="utf-8"))["task"]
        task = (self.tasks / task_name).resolve()
        if task.parent != self.tasks.resolve() or not task.is_dir():
            raise ValueError("Workspace refers to an unknown task")
        for reserved in RESERVED_NAMES:
            if any(path.name == reserved for path in workspace.rglob("*")):
                raise ValueError(f"Workspace contains reserved path: {reserved}")
        for name in REQUIRED_SUBMISSION:
            if not (workspace / name).is_file():
                raise ValueError(f"Missing submission file: {name}")

        proposal = json.loads((workspace / "proposal.json").read_text(encoding="utf-8"))
        required = {"slug", "hypothesis", "expected_direction"}
        if missing := required - proposal.keys():
            raise ValueError(f"Proposal missing fields: {sorted(missing)}")

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        safe_slug = "".join(c for c in proposal["slug"] if c.isalnum() or c in "-_").strip("-_")
        if not safe_slug:
            raise ValueError("Proposal slug has no safe characters")
        run_dir = self.runs / f"{timestamp}-{safe_slug}"
        run_dir.mkdir(parents=True, exist_ok=False)
        shutil.copy2(workspace / "proposal.json", run_dir / "proposal.json")
        shutil.copy2(workspace / "candidate.py", run_dir / "candidate.py")

        evaluator_path = task / "evaluate.py"
        train_files = sorted(path for path in (task / "train").rglob("*") if path.is_file())
        sealed_files = sorted(path for path in (task / "sealed").rglob("*") if path.is_file())
        hashes = {
            "proposal.json": _sha256(run_dir / "proposal.json"),
            "candidate.py": _sha256(run_dir / "candidate.py"),
            "evaluate.py": _sha256(evaluator_path),
            **{f"train/{p.relative_to(task / 'train')}": _sha256(p) for p in train_files},
            **{f"sealed/{p.relative_to(task / 'sealed')}": _sha256(p) for p in sealed_files},
        }
        fingerprint = hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode("utf-8")
        ).hexdigest()

        evaluator = _load_module(evaluator_path, f"evaluator_{fingerprint[:12]}")
        metrics = evaluator.evaluate(run_dir / "candidate.py", task / "sealed")
        result = {
            "task": task_name,
            "run_id": run_dir.name,
            "fingerprint": fingerprint,
            "inputs": hashes,
            "metrics": metrics,
        }
        (run_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        journal = task / "JOURNAL.md"
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n## {run_dir.name}\n\n"
                f"- Hypothesis: {proposal['hypothesis']}\n"
                f"- Expected direction: {proposal['expected_direction']}\n"
                f"- Fingerprint: `{fingerprint}`\n"
                f"- Metrics: `{json.dumps(metrics, sort_keys=True)}`\n"
                f"- Artifact: `runs/{run_dir.name}/result.json`\n"
            )
        return result
