from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceLink(BaseModel):
    evidence_id: str
    path: str
    pointer: str | None = None
    summary: str | None = None


class ApprovalRecord(BaseModel):
    required: bool = True
    approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    notes: str | None = None


class Workspace(BaseModel):
    name: str
    created_at: datetime = Field(default_factory=now_utc)
    customer_alias: str | None = None
    notes: str | None = None
    safety_constraints: list[str] = Field(default_factory=lambda: [
        "read-only AWS collection",
        "no direct cloud mutation",
        "no auto-deploy or auto-merge",
        "human review before customer delivery",
        "human approval before remediation planning and PR/diff generation",
        "AI claims require evidence references",
    ])
    allowed_aws_accounts: list[str] = Field(default_factory=list)
    allowed_regions: list[str] = Field(default_factory=list)
    allowed_repo_paths: list[str] = Field(default_factory=list)
    cost_explorer_policy: Literal["allowed", "not-allowed"] = "allowed"
    ai_policy: Literal["allowed", "not-allowed"] = "allowed"
    analysis_depth: str = "mvp-shallow"
    ai_usage_settings: dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "provider": None})
    human_review_status: str = "not_reviewed"


class SourceEvidence(BaseModel):
    id: str
    source_type: Literal["aws", "repository", "normalized", "graph", "analysis", "ai"]
    collected_at: datetime = Field(default_factory=now_utc)
    workspace: str
    account_id: str | None = None
    region: str | None = None
    service: str | None = None
    collector: str | None = None
    path: str
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AwsResourceObservation(BaseModel):
    id: str
    account_id: str | None = None
    region: str | None = None
    service: str
    resource_type: str
    resource_id: str
    name: str | None = None
    arn: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class AwsRelationshipObservation(BaseModel):
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    confidence: Confidence = Confidence.medium
    evidence: list[EvidenceLink] = Field(default_factory=list)


class RepositoryObservation(BaseModel):
    id: str
    repo_path: str
    file_path: str
    sha256: str
    kind: str
    snippet: str | None = None
    declarations: list[str] = Field(default_factory=list)


class IaCEntity(BaseModel):
    id: str
    source_file: str
    tool: str
    entity_type: str
    name: str
    evidence: list[EvidenceLink] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    kind: str
    label: str
    scope: str
    confidence: Confidence = Confidence.medium
    freshness: str | None = None
    evidence: list[EvidenceLink] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: Confidence = Confidence.medium
    evidence: list[EvidenceLink] = Field(default_factory=list)


class ImpactEstimate(BaseModel):
    cost: str | None = None
    reliability: str | None = None
    security: str | None = None
    operational: str | None = None


class Tradeoff(BaseModel):
    option: str
    upside: str
    downside: str


class Recommendation(BaseModel):
    summary: str
    next_action: str
    alternatives: list[str] = Field(default_factory=list)
    tradeoffs: list[Tradeoff] = Field(default_factory=list)


class EngineeringOpportunity(BaseModel):
    id: str
    title: str
    category: str
    problem: str
    impact: ImpactEstimate = Field(default_factory=ImpactEstimate)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    affected_resources: list[str] = Field(default_factory=list)
    repo_files: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.medium
    severity: str = "medium"
    priority: int = 3
    rationale: str
    recommendation: Recommendation
    assumptions: list[str] = Field(default_factory=list)
    confidence_improvements: list[str] = Field(default_factory=list)
    status: str = "open"
    remediation_supported: bool = True
    pr_diff_status: str = "blocked_pending_human_approval"
    why_wrong: str | None = None


class RemediationPlan(BaseModel):
    id: str
    opportunity_id: str
    scope: list[str]
    non_scope: list[str]
    evidence_links: list[EvidenceLink]
    recommended_path: str
    validation: list[str]
    rollback: list[str]
    risks: list[str]
    approval: ApprovalRecord = Field(default_factory=ApprovalRecord)
    pr_diff_status: str = "blocked_pending_human_approval"


class AIAnalysisArtifact(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=now_utc)
    provider: str | None = None
    model: str | None = None
    skipped: bool = False
    reason: str | None = None
    bounded_context_paths: list[str] = Field(default_factory=list)
    prompts_used: list[str] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    unsupported_assumptions: list[str] = Field(default_factory=list)
