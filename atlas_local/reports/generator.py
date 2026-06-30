from __future__ import annotations

from pathlib import Path

from atlas_local.artifacts import list_artifacts, register_artifact
from atlas_local.storage.jsonio import read_json
from atlas_local.storage.workspace import get_workspace, load_workspace


def _status_for(path: str, artifacts: list[dict]) -> str:
    match = next((a for a in artifacts if a.get("path") == path), None)
    return match.get("status", "draft") if match else "draft"


def _opp_line(o: dict) -> str:
    ev = ", ".join(e.get("path", "") for e in o.get("evidence_links", [])[:2]) or "local normalized evidence"
    return f"- **{o['id']} — {o['title']}** ({o['category']}, {o['confidence']}): {o['problem']} Evidence: `{ev}`. Next: {o['recommendation']['next_action']}"


def _opp_section(o: dict) -> list[str]:
    rec = o.get("recommendation", {})
    impact = o.get("impact") or {}
    evidence = o.get("evidence_links") or []
    tradeoffs = rec.get("tradeoffs") or []
    tradeoff_text = "; ".join(f"{t.get('option')}: {t.get('upside')} / {t.get('downside')}" for t in tradeoffs)
    return [
        f"## {o['id']} — {o['title']}",
        "",
        f"- **Category:** {o.get('category')}",
        f"- **Affected resources:** {', '.join(o.get('affected_resources') or []) or 'None known'}",
        f"- **Files when known:** {', '.join(o.get('repo_files') or []) or 'No linked repository file'}",
        f"- **Problem:** {o.get('problem')}",
        f"- **Impact:** cost={impact.get('cost') or 'n/a'}; reliability={impact.get('reliability') or 'n/a'}; security={impact.get('security') or 'n/a'}; operational={impact.get('operational') or 'n/a'}",
        f"- **Evidence:** {', '.join(e.get('path', '') for e in evidence) or 'Missing direct evidence link'}",
        f"- **Confidence:** {o.get('confidence')} — {o.get('rationale')}",
        f"- **Assumptions:** {'; '.join(o.get('assumptions') or ['None recorded'])}",
        f"- **Why wrong:** {o.get('why_wrong') or 'Customer context may change this conclusion.'}",
        f"- **Confidence improvements:** {'; '.join(o.get('confidence_improvements') or ['Collect customer/runtime context.'])}",
        f"- **Recommendation:** {rec.get('summary')} Next: {rec.get('next_action')}",
        f"- **Alternatives:** {'; '.join(rec.get('alternatives') or ['Defer', 'Investigate manually', 'Do nothing with documented rationale'])}",
        f"- **Tradeoffs:** {tradeoff_text or 'Action reduces risk but requires customer review and operational coordination.'}",
        f"- **Remediation supported:** {'yes' if o.get('remediation_supported') else 'no'}",
        f"- **PR/diff supported:** no — {o.get('pr_diff_status', 'blocked_pending_human_approval')}",
        "- **Human review status:** draft until `atlas mark-reviewed` is run for this report.",
        "",
    ]


def generate_reports(workspace: str) -> Path:
    handle = get_workspace(workspace)
    ws = load_workspace(workspace)
    opps = read_json(handle.path("opportunities", "opportunities.json"), []) or []
    artifacts = list_artifacts(workspace)
    opportunities_path = handle.path("reports", "engineering-opportunities.md")
    readout_path = handle.path("reports", "pilot-readout.md")
    opportunities_md = [
        "# Engineering Opportunities",
        "",
        f"**Human review status:** {_status_for(str(opportunities_path), artifacts)}",
        "",
        "Evidence-backed opportunities generated locally. Human review is required before customer delivery.",
        "",
    ]
    for opp in opps:
        opportunities_md.extend(_opp_section(opp))
    if not opps:
        opportunities_md.append("No deterministic opportunities found yet. Missing evidence may be the reason.")
    handle.path("reports").mkdir(parents=True, exist_ok=True)
    opportunities_path.write_text("\n".join(opportunities_md) + "\n", encoding="utf-8")
    top = opps[:5]
    readout = [
        "# Atlas Local Pilot Readout",
        "",
        f"**Human review status:** {_status_for(str(readout_path), artifacts)}",
        "",
        "## Executive Summary",
        f"Atlas Local analyzed workspace `{ws.name}` for a local, operator-run pilot. Strongest opportunity: {top[0]['title'] if top else 'none yet'}. Decision needed: founder/customer review before delivery or remediation.",
        "",
        "## Scope Analyzed",
        f"Workspace `{ws.name}`; allowed accounts={ws.allowed_aws_accounts or 'not declared'}; regions={ws.allowed_regions or 'from evidence only'}; repositories={ws.allowed_repo_paths or 'local ingested snippets only'}.",
        "",
        "## Connected Scope",
        "- AWS and repository evidence present in the local workspace only.",
        "- Customer/workspace data remains under `.workspaces/` on this machine.",
        "",
        "## Methodology",
        "1. Collect read-only evidence. 2. Normalize resources and IaC. 3. Build Engineering Graph. 4. Run deterministic analyzers. 5. Optionally run bounded AI review.",
        "",
        "## Top Opportunities",
        *( [_opp_line(o) for o in top] or ["- No deterministic opportunities found yet."] ),
        "",
        "## Confidence Summary",
        "Confidence is evidence-bound. Missing Cost Explorer, incomplete repo linkage, skipped AI, or missing customer/runtime context lower confidence.",
        "",
        "## Evidence and Confidence",
        "Every listed opportunity includes evidence links, assumptions, why it might be wrong, and confidence improvements.",
        "",
        "## Readiness Warnings",
        "Run `atlas validate-readiness --workspace <name>` before sharing. Draft artifacts, skipped AI, missing approvals, sensitive findings, and unsupported PR/diff paths may block delivery.",
        "",
        "## Recommended Roadmap",
        "Review, select one remediation candidate, approve planning, validate with customer owners, then rerun Atlas after customer-owned changes.",
        "",
        "## Remediation Candidates",
        "Remediation planning is generated per opportunity only after human approval. No code or cloud changes are applied by Atlas Local.",
        "",
        "## PR or Patch Output",
        "No PR/diff is generated by this scaffold. Any future patch requires explicit approval and normal customer CI/CD.",
        "",
        "## Estimated Impact",
        "Impact is qualitative unless supported by Cost Explorer, usage, runtime, or customer input. Atlas does not invent savings.",
        "",
        "## Risks and Assumptions",
        "Evidence may be incomplete due to AWS permissions, selected regions, or repository scope.",
        "",
        "## Customer Decisions",
        "Accept, reject, defer, investigate, approve remediation planning, or approve future PR/diff generation. Customer retains implementation authority.",
        "",
        "## What Atlas Did Not Do",
        "Atlas did not deploy, mutate cloud resources, bypass CI/CD, merge code, or upload repository content.",
        "",
        "## Next Steps",
        "Review opportunities with the customer, approve remediation planning for selected items, then generate human-reviewed plans.",
    ]
    readout_path.write_text("\n".join(readout) + "\n", encoding="utf-8")
    register_artifact(workspace, "report", opportunities_path)
    register_artifact(workspace, "report", readout_path)
    return readout_path
