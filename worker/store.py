"""Saved task status and results, one JSON file per task in the results/ folder.
The worker writes progress here and the dashboard reads it.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path(task_id: str) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    return RESULTS_DIR / f"{task_id}.json"


def read(task_id: str) -> dict | None:
    try:
        return json.loads(_path(task_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write(task_id: str, **fields) -> dict:
    """Merge fields into the task record and save it atomically."""
    record = read(task_id) or {"task_id": task_id}
    record.update(fields)
    record["updated"] = _now()
    path = _path(task_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return record


def list_recent(limit: int = 20) -> list[dict]:
    RESULTS_DIR.mkdir(exist_ok=True)
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    records = []
    for f in files[:limit]:
        rec = read(f.stem)
        if rec:
            records.append(rec)
    return records