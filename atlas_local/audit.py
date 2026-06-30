from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlas_local.storage.workspace import get_workspace


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_path(workspace: str) -> Path:
    return get_workspace(workspace).path("audit", "audit-log.jsonl")


def record_event(workspace: str, event_type: str, command: str | None = None, **fields: Any) -> Path:
    path = audit_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": now_iso(), "workspace": workspace, "event_type": event_type}
    if command:
        event["command"] = command
    event.update(fields)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    return path


def read_events(workspace: str) -> list[dict[str, Any]]:
    path = audit_path(workspace)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
