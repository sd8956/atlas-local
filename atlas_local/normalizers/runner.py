from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_local.models import AwsResourceObservation, EvidenceLink, IaCEntity
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import get_workspace


def _tags(raw_tags: Any) -> dict[str, str]:
    if isinstance(raw_tags, dict):
        return {str(k): str(v) for k, v in raw_tags.items()}
    if isinstance(raw_tags, list):
        return {str(t.get("Key")): str(t.get("Value")) for t in raw_tags if isinstance(t, dict) and t.get("Key")}
    return {}


def _evidence(path: Path, summary: str) -> EvidenceLink:
    return EvidenceLink(evidence_id=path.stem, path=str(path), summary=summary)


def _add(resources: list[AwsResourceObservation], path: Path, service: str, rtype: str, rid: str | None, name: str | None, region: str | None, tags: Any, attrs: dict[str, Any]):
    if rid:
        resources.append(AwsResourceObservation(
            id=f"aws:{service}:{region or 'global'}:{rid}", service=service, resource_type=rtype, resource_id=str(rid),
            name=name, region=region, tags=_tags(tags), attributes=attrs, evidence=[_evidence(path, f"{service} {rtype}")],
        ))


def normalize_workspace(workspace: str) -> Path:
    handle = get_workspace(workspace)
    resources: list[AwsResourceObservation] = []
    iac: list[IaCEntity] = []
    for path in handle.path("evidence", "raw", "aws").glob("*.json"):
        if path.name == "manifest.json":
            continue
        raw = read_json(path, {})
        service = raw.get("metadata", {}).get("service", "unknown")
        region = raw.get("metadata", {}).get("region")
        items = raw.get("items", {}) or {}
        if service == "ec2":
            for page in items.get("instances") or []:
                for res in page.get("Reservations", []):
                    for inst in res.get("Instances", []):
                        _add(resources, path, service, "instance", inst.get("InstanceId"), None, region, inst.get("Tags"), inst)
            for page in items.get("volumes") or []:
                for vol in page.get("Volumes", []):
                    _add(resources, path, service, "volume", vol.get("VolumeId"), None, region, vol.get("Tags"), vol)
            for page in items.get("security_groups") or []:
                for sg in page.get("SecurityGroups", []):
                    _add(resources, path, service, "security_group", sg.get("GroupId"), sg.get("GroupName"), region, sg.get("Tags"), sg)
            for page in items.get("nat_gateways") or []:
                for nat in page.get("NatGateways", []):
                    _add(resources, path, service, "nat_gateway", nat.get("NatGatewayId"), None, region, nat.get("Tags"), nat)
        elif service == "s3":
            for bucket in (items.get("buckets") or {}).get("Buckets", []):
                _add(resources, path, service, "bucket", bucket.get("Name"), bucket.get("Name"), None, {}, bucket)
        elif service in {"lambda", "rds", "dynamodb", "cloudwatch", "logs"}:
            for value in items.values():
                pages = value if isinstance(value, list) else [value]
                for page in pages:
                    for key, records in (page or {}).items():
                        if isinstance(records, list):
                            for rec in records:
                                if isinstance(rec, dict):
                                    rid = rec.get("FunctionArn") or rec.get("DBInstanceIdentifier") or rec.get("TableName") or rec.get("AlarmName") or rec.get("logGroupName")
                                    _add(resources, path, service, key, rid, rid, region, rec.get("Tags"), rec)
    repo_obs = read_json(handle.path("evidence", "raw", "repository", "observations.json"), []) or []
    for obs in repo_obs:
        for dec in obs.get("declarations", []):
            tool = "terraform" if obs.get("kind") == "terraform" else "cloudformation/cdk"
            iac.append(IaCEntity(id=f"iac:{obs['sha256'][:10]}:{len(iac)}", source_file=obs["file_path"], tool=tool, entity_type=dec.split()[0], name=dec, evidence=[EvidenceLink(evidence_id=obs["id"], path=obs["file_path"], summary=obs.get("kind"))]))
    normalized = {"resources": [r.model_dump(mode="json") for r in resources], "iac_entities": [e.model_dump(mode="json") for e in iac], "repositories": repo_obs, "relationships": []}
    return write_json(handle.path("evidence", "normalized", "normalized.json"), normalized)
