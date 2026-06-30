from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        payload = data.model_dump(mode="json")
    elif isinstance(data, list):
        payload = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in data]
    else:
        payload = data
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
