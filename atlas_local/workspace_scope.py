from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_local.audit import now_iso, record_event
from atlas_local.models import Workspace
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import create_workspace, get_workspace


APPROVAL_TYPES = {"customer-delivery", "remediation-planning", "pr-diff-generation", "ai-use"}
POLICIES = {"allowed", "not-allowed"}


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _split_values(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        result.extend(part.strip() for part in value.split(",") if part.strip())
    return _unique(result)


def load_scope(workspace: str) -> Workspace:
    data = read_json(get_workspace(workspace).path("workspace.json"), {}) or {}
    return Workspace.model_validate(data)


def configure_workspace_scope(
    workspace: str,
    *,
    customer_alias: str,
    allowed_accounts: list[str] | None = None,
    allowed_regions: list[str] | None = None,
    allowed_repo_paths: list[str] | None = None,
    cost_explorer: str,
    ai: str,
) -> Workspace:
    if cost_explorer not in POLICIES:
        raise ValueError("cost-explorer must be 'allowed' or 'not-allowed'")
    if ai not in POLICIES:
        raise ValueError("ai must be 'allowed' or 'not-allowed'")
    handle = create_workspace(workspace)
    current = read_json(handle.path("workspace.json"), {}) or {}
    current.update({
        "name": workspace,
        "customer_alias": customer_alias,
        "allowed_aws_accounts": _split_values(allowed_accounts),
        "allowed_regions": _split_values(allowed_regions),
        "allowed_repo_paths": _split_values(allowed_repo_paths),
        "cost_explorer_policy": cost_explorer,
        "ai_policy": ai,
    })
    current_ai = current.get("ai_usage_settings") or {}
    current_ai["enabled"] = ai == "allowed"
    current["ai_usage_settings"] = current_ai
    scope = Workspace.model_validate(current)
    write_json(handle.path("workspace.json"), scope)
    record_event(workspace, "workspace_scope", command="configure-workspace", result="configured", scope=scope.model_dump(mode="json"))
    return scope


def scope_summary(workspace: str) -> dict[str, Any]:
    scope = load_scope(workspace)
    return {
        "workspace": scope.name,
        "customer_alias": scope.customer_alias,
        "allowed_accounts": scope.allowed_aws_accounts,
        "allowed_regions": scope.allowed_regions,
        "allowed_repo_paths": scope.allowed_repo_paths,
        "ai_policy": scope.ai_policy,
        "cost_explorer_policy": scope.cost_explorer_policy,
        "safety_constraints": scope.safety_constraints,
        "notes": scope.notes,
    }


def is_path_allowed(workspace: str, path: Path) -> bool:
    scope = load_scope(workspace)
    if not scope.allowed_repo_paths:
        return True
    target = path.resolve()
    for allowed in scope.allowed_repo_paths:
        allowed_path = Path(allowed).expanduser().resolve()
        if target == allowed_path or allowed_path in target.parents:
            return True
    return False


def validate_regions(workspace: str, regions: list[str]) -> list[str]:
    scope = load_scope(workspace)
    if not scope.allowed_regions:
        return []
    return [region for region in regions if region not in scope.allowed_regions]


def validate_account(workspace: str, account_id: str | None) -> bool:
    scope = load_scope(workspace)
    return not scope.allowed_aws_accounts or bool(account_id and account_id in scope.allowed_aws_accounts)


def approvals_path(workspace: str) -> Path:
    return get_workspace(workspace).path("approvals", "approvals.json")


def list_approvals(workspace: str) -> list[dict[str, Any]]:
    return read_json(approvals_path(workspace), []) or []


def record_approval(workspace: str, approval_type: str, approved_by: str, note: str, related_artifact: str | None = None, related_opportunity: str | None = None) -> dict[str, Any]:
    if approval_type not in APPROVAL_TYPES:
        raise ValueError(f"approval type must be one of: {', '.join(sorted(APPROVAL_TYPES))}")
    get_workspace(workspace)
    approvals = list_approvals(workspace)
    record = {
        "type": approval_type,
        "approved_by": approved_by,
        "timestamp": now_iso(),
        "note": note,
        "related_artifact": related_artifact,
        "related_opportunity": related_opportunity,
    }
    approvals.append(record)
    write_json(approvals_path(workspace), approvals)
    record_event(workspace, "approval", command="record-approval", result="recorded", approval=record, files_changed=[str(approvals_path(workspace))])
    return record


def latest_approval(workspace: str, approval_type: str) -> dict[str, Any] | None:
    matching = [approval for approval in list_approvals(workspace) if approval.get("type") == approval_type]
    return matching[-1] if matching else None


def approval_trail_lines(workspace: str) -> list[str]:
    approvals = list_approvals(workspace)
    if not approvals:
        return ["- No explicit approval records captured yet."]
    return [
        f"- `{a.get('type')}` — approved_by={a.get('approved_by')}; at={a.get('timestamp')}; note={a.get('note')}"
        + (f"; artifact={a.get('related_artifact')}" if a.get("related_artifact") else "")
        + (f"; opportunity={a.get('related_opportunity')}" if a.get("related_opportunity") else "")
        for a in approvals
    ]
