from __future__ import annotations

from atlas_local.ai.provider import configured_provider
from atlas_local.models import AIAnalysisArtifact
from atlas_local.artifacts import register_artifact
from atlas_local.audit import record_event
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import get_workspace
from atlas_local.workspace_scope import load_scope

PROMPTS = ["cloud_architect_review", "cost_review", "security_advisory_review", "remediation_planning_review", "executive_readout_drafting"]


def _bounded_context(handle, opportunity_id: str | None = None):
    paths = [handle.path("evidence", "normalized", "normalized.json"), handle.path("graph", "engineering-graph.json"), handle.path("opportunities", "opportunities.json")]
    context = {str(p): read_json(p, {}) for p in paths if p.exists()}
    if opportunity_id:
        opp_path = str(handle.path("opportunities", "opportunities.json"))
        opportunities = context.get(opp_path, []) or []
        context[opp_path] = [o for o in opportunities if o.get("id") == opportunity_id]
        graph_path = str(handle.path("graph", "engineering-graph.json"))
        graph = context.get(graph_path, {}) or {}
        selected_resources = set()
        for opp in context[opp_path]:
            selected_resources.update(opp.get("affected_resources", []))
        graph["nodes"] = [n for n in graph.get("nodes", []) if n.get("id") in selected_resources or n.get("kind") in {"region", "iac_entity"}]
        graph["edges"] = [e for e in graph.get("edges", []) if e.get("source") in selected_resources or e.get("target") in selected_resources]
        context[graph_path] = graph
    return context, [str(p) for p in paths if p.exists()]


def preview_ai_context(workspace: str, opportunity_id: str | None = None):
    handle = get_workspace(workspace)
    context, context_paths = _bounded_context(handle, opportunity_id)
    preview = {
        "purpose": "Preview bounded Atlas Local context only; no provider submission is performed.",
        "workspace": workspace,
        "opportunity_id": opportunity_id,
        "bounded_context_paths": context_paths,
        "context": context,
        "safety": [
            "No raw repository source beyond stored observations/snippets.",
            "No cloud mutation, deploy, merge, or CI/CD bypass.",
            "AI output, if later run, is draft reasoning and never approval.",
        ],
    }
    suffix = opportunity_id or "workspace"
    path = handle.path("ai", f"context-preview-{suffix}.json")
    write_json(path, preview)
    register_artifact(workspace, "ai-preview", path, metadata={"opportunity_id": opportunity_id})
    return path


def run_ai_review(workspace: str, provider_name: str | None = None):
    handle = get_workspace(workspace)
    context, context_paths = _bounded_context(handle)
    scope = load_scope(workspace)
    if scope.ai_policy == "not-allowed":
        artifact = AIAnalysisArtifact(id="ai-review-skipped-by-scope", provider=provider_name, skipped=True, reason="AI use is not allowed by workspace scope policy.", bounded_context_paths=context_paths, prompts_used=PROMPTS, unsupported_assumptions=["AI review skipped-by-scope; no provider call was made."])
        path = write_json(handle.path("ai", "ai-review.json"), artifact)
        register_artifact(workspace, "ai-review", path, metadata={"scope_status": "skipped-by-scope"})
        record_event(workspace, "ai", command="ai-review", result="skipped_by_policy", policy=scope.ai_policy, files_changed=[str(path)])
        return path
    provider = configured_provider(provider_name)
    if provider is None:
        artifact = AIAnalysisArtifact(id="ai-review-skipped", provider=provider_name, skipped=True, reason="No AI provider configured. Set ATLAS_AI_API_KEY and configure a provider adapter.", bounded_context_paths=context_paths, prompts_used=PROMPTS, unsupported_assumptions=["No model claims generated."])
    else:
        result = provider.review("Evidence-backed Atlas review only; cite evidence paths for every claim.", context)
        artifact = AIAnalysisArtifact(id="ai-review", provider=provider.name, skipped=False, bounded_context_paths=context_paths, prompts_used=PROMPTS, claims=result.get("claims", []), unsupported_assumptions=result.get("unsupported_assumptions", []))
    path = write_json(handle.path("ai", "ai-review.json"), artifact)
    register_artifact(workspace, "ai-review", path)
    return path
