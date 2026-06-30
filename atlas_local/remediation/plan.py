from __future__ import annotations

from pathlib import Path

from atlas_local.artifacts import register_artifact
from atlas_local.models import RemediationPlan
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import get_workspace


def generate_remediation_plan(workspace: str, opportunity_id: str) -> Path:
    handle = get_workspace(workspace)
    opps = read_json(handle.path("opportunities", "opportunities.json"), []) or []
    opp = next((o for o in opps if o["id"] == opportunity_id), None)
    if not opp:
        raise ValueError(f"Opportunity not found: {opportunity_id}")
    plan = RemediationPlan(id=f"PLAN-{opportunity_id}", opportunity_id=opportunity_id, scope=opp.get("affected_resources", []), non_scope=["No cloud mutation", "No code generation", "No PR/diff until explicit human approval"], evidence_links=opp.get("evidence_links", []), recommended_path=opp["recommendation"]["summary"], validation=["Re-run collection/normalization/analyzers after approved changes", "Confirm customer acceptance criteria"], rollback=["Use provider-native rollback/backups where applicable", "Revert IaC changes through normal review flow if later generated"], risks=[opp.get("why_wrong") or "Evidence may be incomplete"])
    write_json(handle.path("remediation", f"{opportunity_id}.json"), plan)
    ev = "\n".join(f"- `{e.get('path')}` — {e.get('summary', '')}" for e in opp.get("evidence_links", [])) or "- Evidence link unavailable"
    md = f"""# Remediation Plan: {opp['title']}

## Human Approval Required
**Human review status:** draft

This plan is advisory. Atlas Local will not mutate cloud resources or generate PR/diffs without explicit human approval.

## Scope
{chr(10).join(f'- {r}' for r in opp.get('affected_resources', [])) or '- To be confirmed'}

## Non-Scope
- Auto-deploy, auto-merge, CI/CD bypass, or direct cloud mutation.
- Code generation or patch creation in this MVP scaffold.

## Evidence
{ev}

## Recommended Path
{opp['recommendation']['summary']}

## Validation
- Re-run Atlas normalize/build-graph/analyze after approved remediation.
- Validate with service owner and customer acceptance criteria.

## Rollback
- Preserve current state and backups/snapshots where applicable.
- Revert via the customer's normal reviewed workflow.

## Risk
{opp.get('why_wrong') or 'Evidence may be incomplete.'}

## PR/Diff Status
Blocked pending human approval.
"""
    path = handle.path("remediation", f"{opportunity_id}.md")
    path.write_text(md, encoding="utf-8")
    register_artifact(workspace, "remediation-plan", path, metadata={"opportunity_id": opportunity_id})
    return path
