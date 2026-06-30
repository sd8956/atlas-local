from __future__ import annotations

from atlas_local.models import Confidence, EngineeringOpportunity, ImpactEstimate, Recommendation, Tradeoff
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import get_workspace


def _opp_id(prefix: str, idx: int) -> str:
    return f"OPP-{prefix}-{idx:03d}"


def _mark_no_ai(opportunities: list[EngineeringOpportunity]) -> None:
    for opp in opportunities:
        msg = "AI review was intentionally skipped; this is deterministic local analysis only."
        if msg not in opp.assumptions:
            opp.assumptions.append(msg)
        if "Run bounded AI review after preview if AI-backed narrative is desired." not in opp.confidence_improvements:
            opp.confidence_improvements.append("Run bounded AI review after preview if AI-backed narrative is desired.")


def _review_recommendation(summary: str, next_action: str, *, action: str, risk: str) -> Recommendation:
    return Recommendation(
        summary=summary,
        next_action=next_action,
        alternatives=[
            "Defer with documented rationale and revisit after customer context is available.",
            "Investigate manually with the owning team before approving any remediation plan.",
            "Accept current posture if the customer confirms it is intentional and monitored.",
        ],
        tradeoffs=[
            Tradeoff(option=action, upside="Moves the finding toward a reviewed customer decision.", downside=risk),
            Tradeoff(option="Defer", upside="Avoids premature change based on incomplete evidence.", downside="Leaves the observed risk or cost signal unresolved until a later review."),
        ],
    )


def run_analyzers(workspace: str, no_ai: bool = False):
    handle = get_workspace(workspace)
    normalized = read_json(handle.path("evidence", "normalized", "normalized.json"), {"resources": [], "iac_entities": [], "repositories": []})
    graph = read_json(handle.path("graph", "engineering-graph.json"), {"edges": []})
    resources = normalized.get("resources", [])
    iac_text = "\n".join(e.get("name", "") for e in normalized.get("iac_entities", []))
    opportunities: list[EngineeringOpportunity] = []
    idx = 1
    missing_owner = [r for r in resources if not any(k.lower() == "owner" for k in r.get("tags", {}))]
    if missing_owner:
        opportunities.append(EngineeringOpportunity(id=_opp_id("OWN", idx), title="Add owner tags to unowned AWS resources", category="ownership/tagging", problem="Some resources do not expose an Owner tag in collected evidence.", impact=ImpactEstimate(operational="Improves accountability and pilot follow-up routing."), evidence_links=missing_owner[0].get("evidence", []), affected_resources=[r["id"] for r in missing_owner[:20]], confidence=Confidence.high, severity="medium", priority=2, rationale="Atlas saw resources without Owner tags after normalization.", recommendation=_review_recommendation(summary="Define owner tagging standard and remediate missing tags after human approval.", next_action="Review affected resources with the customer and approve a tagging plan.", action="Apply owner tags after approval", risk="Requires agreement on the authoritative ownership taxonomy before changes are planned."), confidence_improvements=["Confirm tag policy or alternate ownership source."], why_wrong="Resources may use a different ownership tag key not yet configured.")); idx += 1
    broad_sg = [r for r in resources if r.get("resource_type") == "security_group" and any(e.get("relationship_type") == "exposes" and e.get("source") == r["id"] for e in graph.get("edges", []))]
    if broad_sg:
        opportunities.append(EngineeringOpportunity(id=_opp_id("SEC", idx), title="Review broadly public security groups", category="networking/security advisory", problem="One or more security groups allow 0.0.0.0/0 according to evidence.", impact=ImpactEstimate(security="May expose services more broadly than intended."), evidence_links=broad_sg[0].get("evidence", []), affected_resources=[r["id"] for r in broad_sg], confidence=Confidence.high, severity="high", priority=1, rationale="Graph contains exposes edges from security groups to public internet.", recommendation=_review_recommendation(summary="Validate intended exposure before narrowing ingress rules.", next_action="Human security review; do not change rules automatically.", action="Narrow ingress after approval", risk="Incorrectly narrowing access can interrupt legitimate customer traffic."), why_wrong="Ingress may be intentionally public, e.g. HTTP/HTTPS load balancer.")); idx += 1
    unattached = [r for r in resources if r.get("resource_type") == "volume" and not r.get("attributes", {}).get("Attachments")]
    if unattached:
        opportunities.append(EngineeringOpportunity(id=_opp_id("COST", idx), title="Review unattached EBS volumes", category="cost", problem="Unattached EBS volumes can incur cost without serving workloads.", impact=ImpactEstimate(cost="Potential savings after snapshot/retention review."), evidence_links=unattached[0].get("evidence", []), affected_resources=[r["id"] for r in unattached], confidence=Confidence.high, severity="medium", priority=2, rationale="EC2 volume evidence includes no attachments.", recommendation=_review_recommendation(summary="Confirm retention needs, snapshot if needed, then plan cleanup.", next_action="Ask customer owner for deletion approval.", action="Snapshot then delete after approval", risk="Deletion without validated backup/retention requirements can cause data loss."), why_wrong="Volume may be intentionally staged for future attachment.")); idx += 1
    stopped = [r for r in resources if r.get("resource_type") == "instance" and r.get("attributes", {}).get("State", {}).get("Name") == "stopped"]
    if stopped:
        opportunities.append(EngineeringOpportunity(id=_opp_id("COST", idx), title="Review stopped EC2 instances", category="cost/scaling", problem="Stopped instances may still carry storage/IP costs and indicate stale capacity.", evidence_links=stopped[0].get("evidence", []), affected_resources=[r["id"] for r in stopped], confidence=Confidence.high, severity="low", priority=3, rationale="Instance state is stopped in AWS evidence.", recommendation=_review_recommendation(summary="Confirm whether instances are still needed.", next_action="Review with workload owner before planning cleanup.", action="Plan retirement after owner approval", risk="Instances may be preserved for rollback, compliance, or scheduled reuse."), why_wrong="Stopped instances may be retained for operational reasons.")); idx += 1
    nats = [r for r in resources if r.get("resource_type") == "nat_gateway"]
    if nats:
        opportunities.append(EngineeringOpportunity(id=_opp_id("COST", idx), title="Review NAT Gateway cost posture", category="cost", problem="NAT Gateways are recurring cost drivers and should be checked against traffic and architecture needs.", evidence_links=nats[0].get("evidence", []), affected_resources=[r["id"] for r in nats], confidence=Confidence.medium, severity="medium", priority=3, rationale="NAT Gateway resources were collected; no traffic data is required to flag for review only.", recommendation=_review_recommendation(summary="Compare NAT count/placement with workload needs and traffic metrics.", next_action="Collect cost/traffic evidence before remediation.", action="Optimize topology after traffic review", risk="Reducing NAT capacity or AZ coverage can harm availability if architecture needs are misunderstood."), assumptions=["Cost impact requires Cost Explorer or VPC flow evidence."], why_wrong="Current NAT topology may be required for availability.")); idx += 1
    if resources and not iac_text:
        opportunities.append(EngineeringOpportunity(id=_opp_id("IAC", idx), title="Link deployed resources to IaC definitions", category="IaC linkage", problem="Atlas found deployed resources but no matching IaC declarations in ingested repository evidence.", impact=ImpactEstimate(operational="Improves safe remediation and change review."), evidence_links=resources[0].get("evidence", []), affected_resources=[r["id"] for r in resources[:20]], confidence=Confidence.medium, severity="medium", priority=2, rationale="Normalized repository evidence contains no IaC entities.", recommendation=_review_recommendation(summary="Ingest the authoritative IaC repo or document manual ownership.", next_action="Confirm repo scope with customer before remediation planning.", action="Ingest authoritative IaC", risk="Additional repository scope requires customer approval and may still miss manually managed resources."), confidence_improvements=["Add Terraform/CDK/CloudFormation repo evidence."], why_wrong="IaC may live in a repo not ingested yet.")); idx += 1
    if no_ai:
        _mark_no_ai(opportunities)
        write_json(handle.path("ai", "ai-review.json"), {
            "id": "ai-review-skipped-no-ai",
            "skipped": True,
            "reason": "--no-ai requested; no provider call was made.",
            "bounded_context_paths": [],
            "unsupported_assumptions": ["No model review was performed; deterministic rules only."],
        })
    return write_json(handle.path("opportunities", "opportunities.json"), opportunities)
