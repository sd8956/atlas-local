from atlas_local.analyzers.runner import run_analyzers
from atlas_local.graph.builder import build_graph_for_workspace
from atlas_local.ingestion.repo import ingest_repository
from atlas_local.normalizers.runner import normalize_workspace
from atlas_local.reports.generator import generate_reports
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.workspace import create_workspace


def sample_ec2_payload():
    return {
        "metadata": {"service": "ec2", "collector": "sample", "account_id": "123", "region": "us-east-1", "read_only": True},
        "items": {
            "instances": [{"Reservations": [{"Instances": [{"InstanceId": "i-001", "State": {"Name": "stopped"}, "Tags": []}]}]}],
            "volumes": [{"Volumes": [{"VolumeId": "vol-001", "Attachments": [], "Tags": []}]}],
            "security_groups": [{"SecurityGroups": [{"GroupId": "sg-001", "GroupName": "open", "IpPermissions": [{"IpRanges": [{"CidrIp": "0.0.0.0/0"}]}], "Tags": []}]}],
            "nat_gateways": [{"NatGateways": [{"NatGatewayId": "nat-001", "Tags": []}]}],
        },
        "errors": [],
    }


def test_workspace_creation_and_raw_evidence_persistence():
    ws = create_workspace("acme")
    assert ws.path("workspace.json").exists()
    path = write_json(ws.path("evidence", "raw", "aws", "ec2-us-east-1-sample.json"), sample_ec2_payload())
    assert read_json(path)["metadata"]["read_only"] is True


def test_normalize_graph_analyze_report_from_sample_evidence():
    ws = create_workspace("acme")
    write_json(ws.path("evidence", "raw", "aws", "ec2-us-east-1-sample.json"), sample_ec2_payload())
    normalize_workspace("acme")
    normalized = read_json(ws.path("evidence", "normalized", "normalized.json"))
    assert len(normalized["resources"]) == 4
    build_graph_for_workspace("acme")
    graph = read_json(ws.path("graph", "engineering-graph.json"))
    assert any(e["relationship_type"] == "exposes" for e in graph["edges"])
    run_analyzers("acme")
    opps = read_json(ws.path("opportunities", "opportunities.json"))
    titles = {o["title"] for o in opps}
    assert "Review broadly public security groups" in titles
    assert "Review unattached EBS volumes" in titles
    generate_reports("acme")
    assert ws.path("reports", "pilot-readout.md").exists()


def test_repository_ingestion_detects_terraform_and_cdk(tmp_path):
    ws = create_workspace("repo")
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    (repo / "main.tf").write_text('resource "aws_s3_bucket" "logs" { bucket = "demo" }\n', encoding="utf-8")
    (repo / "cdk.json").write_text('{"app":"python app.py"}\n', encoding="utf-8")
    ingest_repository("repo", repo)
    obs = read_json(ws.path("evidence", "raw", "repository", "observations.json"))
    assert any(o["kind"] == "terraform" for o in obs)
    assert any(o["kind"] == "cdk-indicator" for o in obs)
