from pathlib import Path

from typer.testing import CliRunner

from atlas_local.artifacts import list_artifacts
from atlas_local.cli.app import app
from atlas_local.storage.jsonio import read_json


runner = CliRunner()


def _ids(workspace="demo"):
    return [a["id"] for a in list_artifacts(workspace) if a["type"] in {"report", "remediation-plan"}]


def _generated_ids(workspace="demo"):
    return [a["id"] for a in list_artifacts(workspace) if a["type"] in {"report", "remediation-plan", "ai-review"}]


def test_sample_demo_workflow_creates_pilot_artifacts():
    assert runner.invoke(app, ["load-sample", "--workspace", "demo"]).exit_code == 0
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0, result.output
    root = Path(".workspaces/demo")
    assert (root / "evidence/raw/aws/ec2-us-east-1.json").exists()
    assert (root / "evidence/raw/repository/observations.json").exists()
    assert (root / "opportunities/opportunities.json").exists()
    assert (root / "reports/pilot-readout.md").exists()
    assert list((root / "remediation").glob("*.md"))


def test_validate_readiness_reports_blockers_and_warnings():
    assert runner.invoke(app, ["init-workspace", "empty"]).exit_code == 0
    result = runner.invoke(app, ["validate-readiness", "--workspace", "empty"])
    assert result.exit_code == 0
    assert "ready: no" in result.output
    assert "missing AWS evidence" in result.output
    assert "recommended_next_action" in result.output


def test_configure_and_show_workspace_scope():
    result = runner.invoke(app, [
        "configure-workspace", "--workspace", "pilot", "--customer-alias", "Acme EU",
        "--allowed-account", "111111111111", "--allowed-region", "eu-west-1",
        "--allowed-repo-path", str(Path.cwd()), "--cost-explorer", "not-allowed", "--ai", "not-allowed",
    ])
    assert result.exit_code == 0, result.output
    shown = runner.invoke(app, ["show-workspace", "--workspace", "pilot"])
    assert shown.exit_code == 0, shown.output
    assert "Acme EU" in shown.output
    assert "eu-west-1" in shown.output
    scope = read_json(Path(".workspaces/pilot/workspace.json"))
    assert scope["cost_explorer_policy"] == "not-allowed"
    assert scope["ai_policy"] == "not-allowed"


def test_ingest_repo_blocks_disallowed_path_when_scope_configured():
    allowed = Path.cwd() / "allowed"
    allowed.mkdir()
    assert runner.invoke(app, [
        "configure-workspace", "--workspace", "scoped", "--customer-alias", "Acme",
        "--allowed-repo-path", str(allowed), "--cost-explorer", "allowed", "--ai", "allowed",
    ]).exit_code == 0
    blocked = runner.invoke(app, ["ingest-repo", "--workspace", "scoped", "--path", str(Path(__file__).parents[1] / "tests" / "sample_data" / "repo")])
    assert blocked.exit_code != 0
    events = Path(".workspaces/scoped/audit/audit-log.jsonl").read_text(encoding="utf-8")
    assert "blocked_disallowed_repo_path" in events


def test_no_ai_analysis_path_records_skipped_ai_assumptions():
    assert runner.invoke(app, ["load-sample", "--workspace", "demo"]).exit_code == 0
    for command in (["normalize", "--workspace", "demo"], ["build-graph", "--workspace", "demo"], ["analyze", "--workspace", "demo", "--no-ai"]):
        assert runner.invoke(app, command).exit_code == 0
    opps = read_json(Path(".workspaces/demo/opportunities/opportunities.json"))
    ai = read_json(Path(".workspaces/demo/ai/ai-review.json"))
    assert ai["skipped"] is True
    assert any("AI review was intentionally skipped" in " ".join(o["assumptions"]) for o in opps)


def test_ai_context_preview_generation_is_bounded_and_scoped():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    opp_id = read_json(Path(".workspaces/demo/opportunities/opportunities.json"))[0]["id"]
    full = runner.invoke(app, ["ai-context-preview", "--workspace", "demo"])
    scoped = runner.invoke(app, ["ai-context-preview", "--workspace", "demo", "--opportunity-id", opp_id])
    assert full.exit_code == 0
    assert scoped.exit_code == 0
    preview = read_json(Path(f".workspaces/demo/ai/context-preview-{opp_id}.json"))
    assert preview["purpose"].startswith("Preview bounded")
    assert preview["opportunity_id"] == opp_id


def test_ai_review_skips_when_workspace_policy_not_allowed():
    assert runner.invoke(app, ["init-workspace", "noai"]).exit_code == 0
    assert runner.invoke(app, [
        "configure-workspace", "--workspace", "noai", "--customer-alias", "Acme",
        "--cost-explorer", "allowed", "--ai", "not-allowed",
    ]).exit_code == 0
    result = runner.invoke(app, ["ai-review", "--workspace", "noai"])
    assert result.exit_code == 0, result.output
    ai = read_json(Path(".workspaces/noai/ai/ai-review.json"))
    assert ai["skipped"] is True
    assert "scope policy" in ai["reason"]
    assert "skipped_by_policy" in Path(".workspaces/noai/audit/audit-log.jsonl").read_text(encoding="utf-8")


def test_cost_explorer_missing_is_skipped_by_scope_when_not_allowed():
    assert runner.invoke(app, ["init-workspace", "nocost"]).exit_code == 0
    assert runner.invoke(app, [
        "configure-workspace", "--workspace", "nocost", "--customer-alias", "Acme",
        "--cost-explorer", "not-allowed", "--ai", "not-allowed",
    ]).exit_code == 0
    result = runner.invoke(app, ["validate-readiness", "--workspace", "nocost"])
    assert result.exit_code == 0, result.output
    assert "Cost Explorer skipped-by-scope" in result.output


def test_audit_log_and_human_review_status_changes():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    artifacts = _ids()
    assert artifacts
    result = runner.invoke(app, ["mark-reviewed", "--workspace", "demo", "--artifact", artifacts[0]])
    assert result.exit_code == 0, result.output
    audit = runner.invoke(app, ["audit-log", "--workspace", "demo"])
    assert audit.exit_code == 0
    assert "mark-reviewed" in audit.output
    updated = next(a for a in list_artifacts("demo") if a["id"] == artifacts[0])
    assert updated["status"] == "founder-reviewed"


def test_approval_records_are_created_and_audited():
    assert runner.invoke(app, ["init-workspace", "approval"]).exit_code == 0
    result = runner.invoke(app, [
        "record-approval", "--workspace", "approval", "--type", "customer-delivery",
        "--approved-by", "Founder", "--note", "Customer package reviewed",
    ])
    assert result.exit_code == 0, result.output
    approvals = read_json(Path(".workspaces/approval/approvals/approvals.json"))
    assert approvals[0]["type"] == "customer-delivery"
    assert "record-approval" in Path(".workspaces/approval/audit/audit-log.jsonl").read_text(encoding="utf-8")


def test_readiness_blocks_without_required_approvals():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    for artifact_id in _ids():
        assert runner.invoke(app, ["mark-reviewed", "--workspace", "demo", "--artifact", artifact_id]).exit_code == 0
    result = runner.invoke(app, ["validate-readiness", "--workspace", "demo"])
    assert result.exit_code == 0, result.output
    compact = result.output.replace("\n", "")
    assert "missing customer-delivery approval" in compact
    assert "missing remediation-planning approval" in compact


def test_readiness_passes_delivery_gate_with_approvals_and_reviewed_artifacts():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    for artifact_id in _generated_ids():
        assert runner.invoke(app, ["mark-reviewed", "--workspace", "demo", "--artifact", artifact_id]).exit_code == 0
    for approval_type in ["customer-delivery", "remediation-planning", "ai-use"]:
        assert runner.invoke(app, [
            "record-approval", "--workspace", "demo", "--type", approval_type,
            "--approved-by", "Founder", "--note", f"Approved {approval_type}",
        ]).exit_code == 0
    result = runner.invoke(app, ["validate-readiness", "--workspace", "demo"])
    assert result.exit_code == 0, result.output
    assert "ready: yes" in result.output


def test_delivery_package_blocks_until_reviewed_then_excludes_raw_evidence():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    blocked = runner.invoke(app, ["package-delivery", "--workspace", "demo"])
    assert blocked.exit_code != 0
    for artifact_id in _ids():
        assert runner.invoke(app, ["mark-reviewed", "--workspace", "demo", "--artifact", artifact_id]).exit_code == 0
    still_blocked = runner.invoke(app, ["package-delivery", "--workspace", "demo"])
    assert still_blocked.exit_code != 0
    assert runner.invoke(app, [
        "record-approval", "--workspace", "demo", "--type", "customer-delivery",
        "--approved-by", "Founder", "--note", "Delivery package approved",
    ]).exit_code == 0
    packaged = runner.invoke(app, ["package-delivery", "--workspace", "demo"])
    assert packaged.exit_code == 0, packaged.output
    root = Path(".workspaces/demo/delivery/demo-atlas-pilot")
    assert (root / "README.md").exists()
    assert (root / "pilot-readout.md").exists()
    assert (root / "engineering-opportunities.md").exists()
    assert (root / "remediation-plans").is_dir()
    assert "Raw AWS" in (root / "evidence-summary.md").read_text(encoding="utf-8")
    assert "Customer owns every implementation decision" in (root / "next-steps.md").read_text(encoding="utf-8")
    assert "artifact-manifest.json" in (root / "README.md").read_text(encoding="utf-8")
    assert (root / "workspace-scope.json").exists()
    assert (root / "approvals.json").exists()
    assert "customer-delivery" in (root / "README.md").read_text(encoding="utf-8")
    for md in [root / "pilot-readout.md", root / "engineering-opportunities.md", *sorted((root / "remediation-plans").glob("*.md"))]:
        text = md.read_text(encoding="utf-8")
        assert "Human review status:** founder-reviewed" in text
        assert "Human review status:** draft" not in text
    assert not (root / "evidence" ).exists()


def test_opportunity_source_json_includes_alternatives_and_tradeoffs():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    opps = read_json(Path(".workspaces/demo/opportunities/opportunities.json"))
    assert opps
    for opp in opps:
        recommendation = opp["recommendation"]
        assert recommendation["alternatives"]
        assert recommendation["tradeoffs"]
        assert all(t["option"] and t["upside"] and t["downside"] for t in recommendation["tradeoffs"])


def test_artifact_metadata_file_exists_and_drives_list_artifacts():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    metadata_path = Path(".workspaces/demo/artifacts/metadata.json")
    assert metadata_path.exists()
    metadata = read_json(metadata_path)
    listed = list_artifacts("demo")
    assert metadata
    assert {a["id"] for a in metadata} == {a["id"] for a in listed}
    assert all(a["path"] and a["status"] for a in metadata)


def test_delete_workspace_requires_exact_confirmation():
    assert runner.invoke(app, ["init-workspace", "danger"]).exit_code == 0
    wrong = runner.invoke(app, ["delete-workspace", "danger"], input="delete danger\n")
    assert wrong.exit_code != 0
    assert Path(".workspaces/danger").exists()
    right = runner.invoke(app, ["delete-workspace", "danger"], input="DELETE danger\n")
    assert right.exit_code == 0, right.output
    assert not Path(".workspaces/danger").exists()


def test_report_sections_required_for_customer_delivery():
    assert runner.invoke(app, ["demo"]).exit_code == 0
    opportunities = Path(".workspaces/demo/reports/engineering-opportunities.md").read_text(encoding="utf-8")
    readout = Path(".workspaces/demo/reports/pilot-readout.md").read_text(encoding="utf-8")
    for required in ["Problem", "Impact", "Evidence", "Confidence", "Assumptions", "Why wrong", "Recommendation", "Alternatives", "Tradeoffs", "Remediation supported", "PR/diff supported", "Human review status"]:
        assert required in opportunities
    for required in ["Executive Summary", "Scope Analyzed", "Methodology", "Top Opportunities", "Confidence Summary", "Readiness Warnings", "Remediation Candidates", "Risks and Assumptions", "What Atlas Did Not Do", "Next Steps"]:
        assert required in readout
