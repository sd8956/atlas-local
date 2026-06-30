from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import boto3

from atlas_local.audit import record_event
from atlas_local.collectors.aws.services import COLLECTORS
from atlas_local.models import SourceEvidence
from atlas_local.storage.jsonio import write_json
from atlas_local.storage.workspace import get_workspace
from atlas_local.workspace_scope import validate_account, validate_regions


def _evidence_id(service: str, region: str | None, payload: dict[str, Any]) -> str:
    raw = f"{service}:{region}:{payload.get('metadata', {}).get('collected_at')}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def collect_aws(workspace: str, profile: str, regions: list[str]) -> Path:
    handle = get_workspace(workspace)
    disallowed_regions = validate_regions(workspace, regions)
    if disallowed_regions:
        record_event(workspace, "scope_block", command="collect-aws", params={"workspace": workspace, "regions": regions}, result="blocked_disallowed_regions", disallowed_regions=disallowed_regions)
        raise PermissionError("Requested AWS region(s) outside configured workspace scope: " + ", ".join(disallowed_regions))
    session = boto3.Session(profile_name=profile)
    try:
        account_id = session.client("sts").get_caller_identity().get("Account")
    except Exception as exc:  # pragma: no cover - depends on local AWS setup
        account_id = None
        record_event(workspace, "scope_warning", command="collect-aws", params={"workspace": workspace}, result="account_identity_unavailable", warning=str(exc))
    if not validate_account(workspace, account_id):
        record_event(workspace, "scope_block", command="collect-aws", params={"workspace": workspace}, result="blocked_disallowed_account", account_id=account_id)
        raise PermissionError(f"AWS account outside configured workspace scope: {account_id or 'unknown'}")
    manifest: list[dict[str, Any]] = []
    for collector in COLLECTORS:
        target_regions = regions if collector.regional else [None]
        for region in target_regions:
            payload = collector.collect(session, region)
            evidence_id = _evidence_id(collector.service, region, payload)
            path = handle.path("evidence", "raw", "aws", f"{collector.service}-{region or 'global'}-{evidence_id}.json")
            write_json(path, payload)
            meta = payload.get("metadata", {})
            manifest.append(SourceEvidence(
                id=evidence_id,
                source_type="aws",
                workspace=workspace,
                account_id=meta.get("account_id"),
                region=meta.get("region"),
                service=meta.get("service"),
                collector=meta.get("collector"),
                path=str(path),
                errors=payload.get("errors", []),
                metadata=meta,
            ).model_dump(mode="json"))
    return write_json(handle.path("evidence", "raw", "aws", "manifest.json"), manifest)
