"""A plain-file journal. Your data stays in one folder you can read and delete."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def home() -> Path:
    p = Path(os.environ.get("GRASSPASS_HOME", Path.home() / ".grasspass"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_config() -> dict:
    f = home() / "config.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(cfg: dict) -> None:
    (home() / "config.json").write_text(json.dumps(cfg, indent=2))


def _file() -> Path:
    return home() / "journal.jsonl"


def load() -> list[dict]:
    f = _file()
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]


def _write_all(entries: list[dict]) -> None:
    _file().write_text("".join(json.dumps(e) + "\n" for e in entries))


def next_id() -> int:
    return max((e["id"] for e in load()), default=0) + 1


def add(entry: dict) -> None:
    entries = load()
    entries.append(entry)
    _write_all(entries)


def mark_done(entry_id: int, minutes_outside: int, note: str, when: datetime) -> dict:
    entries = load()
    for e in entries:
        if e["id"] == entry_id:
            e["status"] = "done"
            e["minutes_outside"] = minutes_outside
            e["note"] = note
            e["done_at"] = when.isoformat(timespec="minutes")
            _write_all(entries)
            return e
    raise KeyError(entry_id)


def stats() -> dict:
    entries = load()
    done = [e for e in entries if e["status"] == "done"]
    outside = sum(e.get("minutes_outside") or 0 for e in done)
    screen = sum(e.get("gen_seconds") or 0.0 for e in entries)
    return {
        "issued": len(entries),
        "done": len(done),
        "minutes_outside": outside,
        "generating_seconds": round(screen, 1),
    }
