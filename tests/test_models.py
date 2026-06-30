from atlas_local.models import EngineeringOpportunity, Recommendation, Workspace


def test_workspace_defaults_capture_safety_boundaries():
    ws = Workspace(name="acme")
    assert "no direct cloud mutation" in ws.safety_constraints
    assert ws.human_review_status == "not_reviewed"


def test_opportunity_requires_recommendation():
    opp = EngineeringOpportunity(id="OPP-1", title="Missing tags", category="ownership", problem="No Owner tag", rationale="Evidence showed missing tags", recommendation=Recommendation(summary="Add tags", next_action="Review owners"))
    assert opp.pr_diff_status == "blocked_pending_human_approval"
