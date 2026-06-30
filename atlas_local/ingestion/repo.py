from __future__ import annotations

import hashlib
from pathlib import Path

from atlas_local.models import RepositoryObservation
from atlas_local.audit import record_event
from atlas_local.storage.jsonio import write_json
from atlas_local.storage.workspace import get_workspace
from atlas_local.workspace_scope import is_path_allowed

INTERESTING = {".tf", ".tfvars", ".yaml", ".yml", ".json", ".py", ".toml", ".txt"}
CDK_NAMES = {"cdk.json", "package.json", "pyproject.toml", "requirements.txt", "app.py"}


def _kind(path: Path) -> str:
    if path.suffix in {".tf", ".tfvars"}:
        return "terraform"
    if path.name in CDK_NAMES or any(part in {"bin", "lib"} for part in path.parts):
        return "cdk-indicator"
    if path.suffix in {".yaml", ".yml", ".json"}:
        return "cloudformation-or-config"
    return "repository-file"


def _declarations(text: str) -> list[str]:
    declarations: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("resource ") or stripped.startswith("module ") or stripped.startswith("class "):
            declarations.append(stripped[:160])
        if "AWS::" in stripped:
            declarations.append(stripped[:160])
    return declarations[:20]


def ingest_repository(workspace: str, path: Path) -> Path:
    handle = get_workspace(workspace)
    root = path.resolve()
    if not is_path_allowed(workspace, root):
        record_event(workspace, "scope_block", command="ingest-repo", params={"workspace": workspace, "path": str(root)}, result="blocked_disallowed_repo_path")
        raise PermissionError(f"Repository path is outside configured workspace scope: {root}")
    observations: list[RepositoryObservation] = []
    for file in root.rglob("*"):
        if not file.is_file() or file.suffix not in INTERESTING and file.name not in CDK_NAMES:
            continue
        rel = str(file.relative_to(root))
        content = file.read_bytes()
        text = content.decode("utf-8", errors="ignore")
        sha = hashlib.sha256(content).hexdigest()
        observations.append(RepositoryObservation(
            id=f"repo:{sha[:12]}", repo_path=str(root), file_path=rel, sha256=sha, kind=_kind(file),
            snippet="\n".join(text.splitlines()[:20])[:2000], declarations=_declarations(text),
        ))
    return write_json(handle.path("evidence", "raw", "repository", "observations.json"), observations)
