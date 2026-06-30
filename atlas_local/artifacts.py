from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from atlas_local.audit import now_iso, record_event
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import get_workspace


REVIEWED_STATUSES = {"founder-reviewed", "customer-ready", "delivered"}


def _metadata_path(workspace: str) -> Path:
    return get_workspace(workspace).path("artifacts", "metadata.json")


def _legacy_metadata_path(workspace: str) -> Path:
    return get_workspace(workspace).path("audit", "artifacts.json")


def _write_metadata(workspace: str, artifacts: list[dict[str, Any]]) -> None:
    write_json(_metadata_path(workspace), artifacts)
    # Keep the earlier audit-local metadata location synchronized for any
    # existing callers or scripts while exposing a discoverable artifacts file.
    write_json(_legacy_metadata_path(workspace), artifacts)


def _artifact_id(artifact_type: str, path: Path) -> str:
    digest = hashlib.sha1(f"{artifact_type}:{path}".encode("utf-8")).hexdigest()[:10]
    return f"ART-{digest}"


def list_artifacts(workspace: str) -> list[dict[str, Any]]:
    artifacts = read_json(_metadata_path(workspace), None)
    if artifacts is None:
        artifacts = read_json(_legacy_metadata_path(workspace), []) or []
        if artifacts:
            _write_metadata(workspace, artifacts)
    return sorted(artifacts, key=lambda a: (a.get("type", ""), a.get("path", "")))


def register_artifact(workspace: str, artifact_type: str, path: Path, *, status: str = "draft", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    root = get_workspace(workspace).root
    rel = str(path if not path.is_absolute() else path.relative_to(Path.cwd()))
    artifact_id = _artifact_id(artifact_type, Path(rel))
    artifacts = list_artifacts(workspace)
    existing = next((a for a in artifacts if a["id"] == artifact_id), None)
    stat = path.stat() if path.exists() else None
    payload = {
        "id": artifact_id,
        "type": artifact_type,
        "status": existing.get("status", status) if existing else status,
        "path": rel,
        "generated_at": existing.get("generated_at") if existing else now_iso(),
        "updated_at": now_iso(),
        "superseded_by": None,
        "reviewed_by": existing.get("reviewed_by") if existing else None,
        "reviewed_at": existing.get("reviewed_at") if existing else None,
        "size_bytes": stat.st_size if stat else None,
        "metadata": metadata or {},
    }
    if existing:
        artifacts = [payload if a["id"] == artifact_id else a for a in artifacts]
    else:
        artifacts.append(payload)
    _write_metadata(workspace, artifacts)
    record_event(workspace, "artifact", files_changed=[rel], artifact_ids=[artifact_id], artifact_type=artifact_type, status=payload["status"])
    return payload


def mark_reviewed(workspace: str, artifact_id: str, reviewer: str = "founder") -> dict[str, Any]:
    artifacts = list_artifacts(workspace)
    artifact = next((a for a in artifacts if a["id"] == artifact_id), None)
    if artifact is None:
        raise ValueError(f"Artifact not found: {artifact_id}")
    old = artifact.get("status", "draft")
    artifact["status"] = "founder-reviewed"
    artifact["reviewed_by"] = reviewer
    artifact["reviewed_at"] = now_iso()
    artifact["updated_at"] = artifact["reviewed_at"]
    _write_metadata(workspace, artifacts)
    record_event(workspace, "review", command="mark-reviewed", artifact_ids=[artifact_id], old_status=old, new_status=artifact["status"], reviewer=reviewer)
    return artifact


def required_delivery_artifacts(workspace: str) -> list[dict[str, Any]]:
    artifacts = list_artifacts(workspace)
    return [a for a in artifacts if a.get("type") in {"report", "remediation-plan"}]
