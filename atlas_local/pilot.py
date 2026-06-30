from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from atlas_local.ai.review import preview_ai_context, run_ai_review
from atlas_local.analyzers.runner import run_analyzers
from atlas_local.artifacts import REVIEWED_STATUSES, list_artifacts, register_artifact, required_delivery_artifacts
from atlas_local.audit import record_event
from atlas_local.graph.builder import build_graph_for_workspace
from atlas_local.ingestion.repo import ingest_repository
from atlas_local.normalizers.runner import normalize_workspace
from atlas_local.remediation.plan import generate_remediation_plan
from atlas_local.reports.generator import generate_reports
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import create_workspace, get_workspace
from atlas_local.workspace_scope import approval_trail_lines, latest_approval, list_approvals, load_scope, scope_summary


SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "sample_data"


def _artifact_for_path(artifacts: list[dict[str, Any]], path: Path) -> dict[str, Any] | None:
    return next((a for a in artifacts if a.get("path") == str(path)), None)


def _copy_markdown_with_review_status(src: Path, dest: Path, artifacts: list[dict[str, Any]]) -> None:
    artifact = _artifact_for_path(artifacts, src)
    status = artifact.get("status", "draft") if artifact else "draft"
    text = src.read_text(encoding="utf-8")
    lines = []
    replaced = False
    for line in text.splitlines():
        normalized = line.replace("**", "").strip().lower()
        if "human review status:" in normalized:
            lines.append(f"**Human review status:** {status}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.insert(1, f"\n**Human review status:** {status}")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _artifact_review_trail(artifacts: list[dict[str, Any]]) -> list[str]:
    relevant = [a for a in artifacts if a.get("type") in {"report", "remediation-plan"}]
    if not relevant:
        return ["- No report/remediation approvals recorded yet."]
    return [
        f"- `{a.get('id')}` `{a.get('path')}` — {a.get('status')}"
        f"; reviewed_by={a.get('reviewed_by') or 'n/a'}; reviewed_at={a.get('reviewed_at') or 'n/a'}"
        for a in relevant
    ]


def _delivery_readme(workspace: str, artifacts: list[dict[str, Any]]) -> str:
    summary = scope_summary(workspace)
    return "\n".join([
        "# Atlas Pilot Delivery Package",
        "",
        "Atlas Local found review-ready engineering opportunities from local evidence and packaged the human-reviewed summaries for customer discussion.",
        "",
        "## Analyzed Scope",
        f"- Workspace: `{workspace}`",
        f"- Customer alias: {summary.get('customer_alias') or 'not declared'}",
        f"- AWS accounts: {summary.get('allowed_accounts') or 'not declared in workspace metadata'}",
        f"- Regions: {summary.get('allowed_regions') or 'from collected evidence only'}",
        f"- Repository scope: {summary.get('allowed_repo_paths') or 'local ingested snippets only'}",
        f"- AI policy: {summary.get('ai_policy')}",
        f"- Cost Explorer policy: {summary.get('cost_explorer_policy')}",
        "",
        "## Safety Boundary",
        "Atlas was run locally by an operator with read-only evidence collection. This package does not include raw AWS payloads or full repository source by default.",
        "",
        "## Package Contents",
        "- `pilot-readout.md` — customer-facing pilot summary.",
        "- `engineering-opportunities.md` — opportunity detail with assumptions, alternatives, and tradeoffs.",
        "- `remediation-plans/` — advisory plans generated only for selected reviewed opportunities.",
        "- `evidence-summary.md` — safe evidence scope summary without raw evidence disclosure.",
        "- `next-steps.md` — customer decision paths and approval gates.",
        f"- `artifact-manifest.json` — package manifest copied from `.workspaces/{workspace}/artifacts/metadata.json`.",
        "",
        "## Approval / Review Status",
        "### Artifact review",
        *_artifact_review_trail(artifacts),
        "",
        "### Explicit approvals",
        *approval_trail_lines(workspace),
        "",
        "## What Atlas Did Not Do",
        "- Did not mutate AWS resources, deploy, merge, auto-remediate, or bypass CI/CD.",
        "- Did not upload repository content or expose raw AWS evidence in this package.",
        "- Did not produce PRs/diffs without explicit human approval.",
        "",
    ])


def _evidence_summary(workspace: str, artifacts: list[dict[str, Any]]) -> str:
    handle = get_workspace(workspace)
    scope = load_scope(workspace)
    aws_files = sorted(p.name for p in handle.path("evidence", "raw", "aws").glob("*.json"))
    repo_obs = read_json(handle.path("evidence", "raw", "repository", "observations.json"), []) or []
    generated = [a for a in artifacts if a.get("type") in {"report", "remediation-plan", "ai-review"}]
    return "\n".join([
        "# Evidence Summary",
        "",
        "Atlas analyzed local evidence summaries and generated artifacts. Raw AWS payloads and full repository source are excluded from this delivery package by default.",
        "",
        "## Evidence Analyzed",
        f"- AWS evidence files present locally: {len(aws_files)} collected JSON file(s).",
        f"- Repository observations present locally: {len(repo_obs)} file observation(s), summarized only.",
        "- Normalized resources, graph relationships, deterministic opportunities, and optional AI review outputs stored under the workspace.",
        "",
        "## Missing or Skipped Evidence",
        "- Cost Explorer: " + ("skipped-by-scope (workspace policy not-allowed)." if scope.cost_explorer_policy == "not-allowed" else "may be missing unless separately provided; cost claims must stay qualitative."),
        "- Runtime traffic, service-owner intent, and full customer architecture context may be missing unless separately provided.",
        "- Raw AWS evidence and full repository source were intentionally skipped for customer package disclosure.",
        "",
        "## Generated Artifact References",
        *(f"- `{a.get('path')}` — {a.get('type')} / {a.get('status')}" for a in generated),
        f"- Metadata source: `.workspaces/{workspace}/artifacts/metadata.json`; package copy: `artifact-manifest.json`.",
        "",
        "## Approval Trail",
        *_artifact_review_trail(artifacts),
        "",
        "## Explicit Approval Records",
        *approval_trail_lines(workspace),
        "",
    ])


def _next_steps(workspace: str, artifacts: list[dict[str, Any]]) -> str:
    return "\n".join([
        "# Next Steps",
        "",
        "Customer owns every implementation decision. Atlas Local only prepares evidence-backed recommendations and advisory plans.",
        "",
        "| Decision | When to choose it | What happens next | Approval required |",
        "| --- | --- | --- | --- |",
        "| Stop | Findings are not relevant or scope is wrong. | Close the pilot package with documented rationale. | Customer decision. |",
        "| Investigate more | Evidence is incomplete or confidence needs improvement. | Collect approved extra context, then rerun Atlas locally. | Customer approval for extra scope. |",
        "| Approve remediation planning | A finding is worth deeper planning. | Generate/refine advisory plans for selected opportunities. | Human review before sharing. |",
        "| Approve PR/diff generation | Customer wants implementation artifacts. | Produce reviewed diffs through normal customer workflow only. | Explicit human approval and customer CI/CD. |",
        "| Continue another pilot | More accounts, regions, or repos should be assessed. | Start a new bounded local workspace/scope. | Customer scope approval. |",
        "| Convert to recurring usage | Customer wants repeated local reviews. | Define cadence, evidence boundaries, and review owners. | Customer operating agreement. |",
        "",
        "## Current Approval Trail",
        *_artifact_review_trail(artifacts),
        "",
        "## Explicit Approval Records",
        *approval_trail_lines(workspace),
        "",
    ])


def load_sample(workspace: str) -> list[Path]:
    handle = create_workspace(workspace)
    created: list[Path] = []
    aws_src = SAMPLE_ROOT / "aws"
    if aws_src.exists():
        for src in aws_src.glob("*.json"):
            dest = handle.path("evidence", "raw", "aws", src.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            created.append(dest)
    repo_src = SAMPLE_ROOT / "repo"
    if repo_src.exists():
        ingest_repository(workspace, repo_src)
        created.append(handle.path("evidence", "raw", "repository", "observations.json"))
    record_event(workspace, "command", command="load-sample", params={"workspace": workspace}, result="success", files_changed=[str(p) for p in created])
    return created


def run_demo(workspace: str = "demo") -> dict[str, Path | None]:
    load_sample(workspace)
    normalized = normalize_workspace(workspace)
    graph = build_graph_for_workspace(workspace)
    opportunities = run_analyzers(workspace, no_ai=True)
    ai = run_ai_review(workspace)
    readout = generate_reports(workspace)
    opps = read_json(get_workspace(workspace).path("opportunities", "opportunities.json"), []) or []
    remediation = generate_remediation_plan(workspace, opps[0]["id"]) if opps else None
    result = {"normalized": normalized, "graph": graph, "opportunities": opportunities, "ai": ai, "readout": readout, "remediation": remediation}
    record_event(workspace, "command", command="demo", params={"workspace": workspace}, result="success", files_changed=[str(p) for p in result.values() if p])
    return result


def validate_readiness(workspace: str) -> dict[str, Any]:
    handle = get_workspace(workspace)
    blockers: list[str] = []
    warnings: list[str] = []
    skipped_by_scope: list[str] = []
    scope = load_scope(workspace)
    aws_files = list(handle.path("evidence", "raw", "aws").glob("*.json"))
    repo_obs = read_json(handle.path("evidence", "raw", "repository", "observations.json"), []) or []
    normalized = read_json(handle.path("evidence", "normalized", "normalized.json"), {}) or {}
    opps = read_json(handle.path("opportunities", "opportunities.json"), []) or []
    ai = read_json(handle.path("ai", "ai-review.json"), {}) or {}
    artifacts = list_artifacts(workspace)
    aws_manifest = read_json(handle.path("evidence", "raw", "aws", "manifest.json"), []) or []
    if not aws_files:
        blockers.append("missing AWS evidence")
    if not repo_obs:
        warnings.append("missing repository evidence or approved CDK/Terraform context")
    if not normalized.get("resources"):
        blockers.append("missing normalized AWS resources")
    if scope.allowed_aws_accounts:
        seen_accounts = {entry.get("account_id") for entry in aws_manifest if entry.get("account_id")}
        outside_accounts = sorted(account for account in seen_accounts if account not in scope.allowed_aws_accounts)
        if outside_accounts:
            blockers.append("AWS evidence outside allowed accounts: " + ", ".join(outside_accounts))
            record_event(workspace, "scope_block", command="validate-readiness", result="evidence_outside_allowed_accounts", account_ids=outside_accounts)
        elif not seen_accounts and aws_files:
            warnings.append("workspace scope declares allowed accounts, but collected evidence account identity is unavailable")
            record_event(workspace, "scope_warning", command="validate-readiness", result="account_identity_unavailable_for_evidence_scope")
    if scope.allowed_regions:
        seen_regions = {entry.get("region") for entry in aws_manifest if entry.get("region")}
        outside_regions = sorted(region for region in seen_regions if region not in scope.allowed_regions)
        if outside_regions:
            blockers.append("AWS evidence outside allowed regions: " + ", ".join(outside_regions))
            record_event(workspace, "scope_block", command="validate-readiness", result="evidence_outside_allowed_regions", regions=outside_regions)
    if not opps:
        blockers.append("no engineering opportunities generated")
    if any(o.get("confidence") == "low" for o in opps):
        warnings.append("low-confidence opportunities require investigation before delivery")
    if scope.cost_explorer_policy == "not-allowed":
        skipped_by_scope.append("Cost Explorer skipped-by-scope (workspace policy not-allowed)")
        record_event(workspace, "scope_warning", command="validate-readiness", result="cost_explorer_skipped_by_scope", policy=scope.cost_explorer_policy)
    elif any("cost" in (o.get("category") or "").lower() for o in opps):
        warnings.append("Cost Explorer/usage evidence may be incomplete; cost claims must stay qualitative")
    if any(any(word in (o.get("category", "") + " " + o.get("title", "")).lower() for word in ["iam", "security", "network", "public", "encryption", "retention", "deletion"]) for o in opps):
        warnings.append("sensitive findings require stronger human/customer review")
    if scope.ai_policy == "not-allowed":
        skipped_by_scope.append("AI use skipped-by-scope (workspace policy not-allowed)")
        if not ai:
            record_event(workspace, "ai", command="validate-readiness", result="ai_skipped_by_policy", policy=scope.ai_policy)
    elif not ai:
        warnings.append("AI not run; deterministic analysis only")
    elif ai.get("skipped"):
        reason = ai.get("reason")
        if "scope" in (reason or "").lower():
            skipped_by_scope.append(f"AI skipped-by-scope: {reason}")
        else:
            warnings.append(f"AI skipped: {reason}")
    if any(a.get("status") == "draft" for a in artifacts if a.get("type") in {"report", "remediation-plan", "ai-review"}):
        blockers.append("missing founder review for generated artifacts")
    if any(o.get("pr_diff_status", "").startswith("blocked") for o in opps):
        warnings.append("PR/diff generation unsupported or blocked pending explicit approval")
    if not any(a.get("status") in REVIEWED_STATUSES for a in artifacts):
        blockers.append("missing approvals/customer-ready artifacts")
    if not latest_approval(workspace, "customer-delivery"):
        blockers.append("missing customer-delivery approval")
    if handle.path("remediation").exists() and list(handle.path("remediation").glob("*.md")) and not latest_approval(workspace, "remediation-planning"):
        blockers.append("missing remediation-planning approval")
    if any(o.get("pr_diff_status", "").startswith("blocked") for o in opps) and not latest_approval(workspace, "pr-diff-generation"):
        warnings.append("PR/diff generation unsupported and missing pr-diff-generation approval")
    if scope.ai_policy == "allowed" and (scope.ai_usage_settings.get("enabled") or ai) and not latest_approval(workspace, "ai-use"):
        blockers.append("missing ai-use approval")
    record_event(workspace, "readiness", command="validate-readiness", result="approval_checks", approvals={"customer_delivery": bool(latest_approval(workspace, "customer-delivery")), "remediation_planning": bool(latest_approval(workspace, "remediation-planning")), "pr_diff_generation": bool(latest_approval(workspace, "pr-diff-generation")), "ai_use": bool(latest_approval(workspace, "ai-use"))})
    ready = not blockers
    next_action = "atlas package-delivery --workspace " + workspace if ready else "resolve blockers, then run atlas validate-readiness --workspace " + workspace
    result = {"ready": "yes" if ready else "no", "blocked_by": blockers, "warnings": warnings, "skipped_by_scope": skipped_by_scope, "recommended_next_action": next_action}
    record_event(workspace, "readiness", command="validate-readiness", params={"workspace": workspace}, result=result)
    return result


def package_delivery(workspace: str) -> Path:
    handle = get_workspace(workspace)
    required = required_delivery_artifacts(workspace)
    unreviewed = [a for a in required if a.get("status") not in REVIEWED_STATUSES]
    if not required:
        raise ValueError("No report/remediation artifacts found. Generate readout and remediation plan first.")
    if unreviewed:
        raise ValueError("Delivery blocked: required artifacts are not founder-reviewed/customer-ready: " + ", ".join(a["id"] for a in unreviewed))
    if not latest_approval(workspace, "customer-delivery"):
        raise ValueError("Delivery blocked: missing customer-delivery approval. Run atlas record-approval --type customer-delivery before packaging.")
    root = handle.path("delivery", f"{workspace}-atlas-pilot")
    plans = root / "remediation-plans"
    plans.mkdir(parents=True, exist_ok=True)
    artifacts = list_artifacts(workspace)
    readout_src = handle.path("reports", "pilot-readout.md")
    opp_src = handle.path("reports", "engineering-opportunities.md")
    if readout_src.exists():
        _copy_markdown_with_review_status(readout_src, root / "pilot-readout.md", artifacts)
    if opp_src.exists():
        _copy_markdown_with_review_status(opp_src, root / "engineering-opportunities.md", artifacts)
    for plan in handle.path("remediation").glob("*.md"):
        _copy_markdown_with_review_status(plan, plans / plan.name, artifacts)
    (root / "README.md").write_text(_delivery_readme(workspace, artifacts), encoding="utf-8")
    (root / "evidence-summary.md").write_text(_evidence_summary(workspace, artifacts), encoding="utf-8")
    (root / "next-steps.md").write_text(_next_steps(workspace, artifacts), encoding="utf-8")
    write_json(root / "workspace-scope.json", scope_summary(workspace))
    write_json(root / "approvals.json", {"approvals": list_approvals(workspace)})
    write_json(root / "artifact-manifest.json", {"workspace": workspace, "metadata_source": str(handle.path("artifacts", "metadata.json")), "included_artifacts": artifacts, "workspace_scope": scope_summary(workspace), "approval_trail": list_approvals(workspace), "excluded": ["raw AWS evidence", "full repository source"]})
    artifact = register_artifact(workspace, "delivery-package", root, status="customer-ready")
    record_event(workspace, "delivery", command="package-delivery", artifact_ids=[artifact["id"]], files_changed=[str(root)], excluded=["raw AWS evidence", "full repository source"])
    return root


def write_ai_preview(workspace: str, opportunity_id: str | None = None) -> Path:
    path = preview_ai_context(workspace, opportunity_id)
    record_event(workspace, "ai", command="ai-context-preview", params={"workspace": workspace, "opportunity_id": opportunity_id}, result="preview_only", files_changed=[str(path)])
    return path
