import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from atlas_local.ai.review import run_ai_review
from atlas_local.analyzers.runner import run_analyzers
from atlas_local.artifacts import list_artifacts, mark_reviewed
from atlas_local.audit import read_events, record_event
from atlas_local.collectors.aws.runner import collect_aws
from atlas_local.graph.builder import build_graph_for_workspace
from atlas_local.ingestion.repo import ingest_repository
from atlas_local.normalizers.runner import normalize_workspace
from atlas_local.pilot import load_sample, package_delivery, run_demo, validate_readiness, write_ai_preview
from atlas_local.remediation.plan import generate_remediation_plan
from atlas_local.reports.generator import generate_reports
from atlas_local.storage.workspace import create_workspace, get_workspace
from atlas_local.workspace_scope import configure_workspace_scope, record_approval, scope_summary

app = typer.Typer(help="Atlas Local: local, evidence-first AWS remediation pilot workflow.")
console = Console()


@app.command("init-workspace")
def init_workspace(workspace_name: str):
    ws = create_workspace(workspace_name)
    console.print(f"[green]Workspace created:[/] {ws.root}")


@app.command("collect-aws")
def collect_aws_cmd(
    workspace: str = typer.Option(..., "--workspace"),
    profile: str = typer.Option(..., "--profile"),
    regions: str = typer.Option(..., "--regions", help="Comma-separated AWS regions"),
):
    result = collect_aws(workspace, profile, [r.strip() for r in regions.split(",") if r.strip()])
    console.print(f"[green]AWS collection complete:[/] {result}")


@app.command("configure-workspace")
def configure_workspace_cmd(
    workspace: str = typer.Option(..., "--workspace"),
    customer_alias: str = typer.Option(..., "--customer-alias"),
    allowed_account: list[str] = typer.Option([], "--allowed-account", help="Allowed AWS account ID. Repeat or provide comma-separated values."),
    allowed_region: list[str] = typer.Option([], "--allowed-region", help="Allowed AWS region. Repeat or provide comma-separated values."),
    allowed_repo_path: list[str] = typer.Option([], "--allowed-repo-path", help="Allowed repository root path. Repeat or provide comma-separated values."),
    cost_explorer: str = typer.Option(..., "--cost-explorer", help="allowed or not-allowed"),
    ai: str = typer.Option(..., "--ai", help="allowed or not-allowed"),
):
    scope = configure_workspace_scope(
        workspace,
        customer_alias=customer_alias,
        allowed_accounts=allowed_account,
        allowed_regions=allowed_region,
        allowed_repo_paths=allowed_repo_path,
        cost_explorer=cost_explorer,
        ai=ai,
    )
    console.print(f"[green]Workspace scope configured:[/] {scope.name}")
    console.print("Repeat --allowed-account/--allowed-region/--allowed-repo-path for multiple values; comma-separated values are also accepted.")


@app.command("show-workspace")
def show_workspace_cmd(workspace: str = typer.Option(..., "--workspace")):
    summary = scope_summary(workspace)
    table = Table("Field", "Value")
    for key, value in summary.items():
        table.add_row(key, "\n".join(value) if isinstance(value, list) else str(value or ""))
    console.print(table)


@app.command("ingest-repo")
def ingest_repo_cmd(workspace: str = typer.Option(..., "--workspace"), path: Path = typer.Option(..., "--path")):
    result = ingest_repository(workspace, path)
    console.print(f"[green]Repository evidence saved:[/] {result}")


@app.command("normalize")
def normalize_cmd(workspace: str = typer.Option(..., "--workspace")):
    result = normalize_workspace(workspace)
    console.print(f"[green]Normalized evidence:[/] {result}")


@app.command("build-graph")
def build_graph_cmd(workspace: str = typer.Option(..., "--workspace")):
    result = build_graph_for_workspace(workspace)
    console.print(f"[green]Engineering graph written:[/] {result}")


@app.command("analyze")
def analyze_cmd(workspace: str = typer.Option(..., "--workspace"), no_ai: bool = typer.Option(False, "--no-ai", help="Run deterministic analysis only; make no AI provider calls.")):
    result = run_analyzers(workspace, no_ai=no_ai)
    record_event(workspace, "command", command="analyze", params={"workspace": workspace, "no_ai": no_ai}, result="success", files_changed=[str(result)], ai="skipped" if no_ai else "not_requested")
    console.print(f"[green]Opportunities written:[/] {result}")


@app.command("ai-review")
def ai_review_cmd(workspace: str = typer.Option(..., "--workspace"), provider: Optional[str] = None):
    result = run_ai_review(workspace, provider_name=provider)
    record_event(workspace, "ai", command="ai-review", params={"workspace": workspace, "provider": provider}, result="success", files_changed=[str(result)])
    console.print(f"[green]AI review artifact written:[/] {result}")


@app.command("generate-readout")
def generate_readout_cmd(workspace: str = typer.Option(..., "--workspace")):
    result = generate_reports(workspace)
    record_event(workspace, "report", command="generate-readout", params={"workspace": workspace}, result="success", files_changed=[str(result)])
    console.print(f"[green]Reports written:[/] {result}")


@app.command("generate-remediation-plan")
def remediation_plan_cmd(
    workspace: str = typer.Option(..., "--workspace"),
    opportunity_id: str = typer.Option(..., "--opportunity-id"),
):
    result = generate_remediation_plan(workspace, opportunity_id)
    record_event(workspace, "remediation", command="generate-remediation-plan", params={"workspace": workspace, "opportunity_id": opportunity_id}, result="success", files_changed=[str(result)])
    console.print(f"[green]Remediation plan written:[/] {result}")


@app.command("load-sample")
def load_sample_cmd(workspace: str = typer.Option(..., "--workspace")):
    files = load_sample(workspace)
    console.print(f"[green]Sample evidence loaded:[/] {len(files)} files into .workspaces/{workspace}")


@app.command("demo")
def demo_cmd(workspace: str = typer.Option("demo", "--workspace", help="Demo workspace name; defaults to demo.")):
    result = run_demo(workspace)
    console.print(f"[green]Demo workflow complete:[/] .workspaces/{workspace}")
    for name, path in result.items():
        if path:
            console.print(f"- {name}: {path}")


@app.command("validate-readiness")
def validate_readiness_cmd(workspace: str = typer.Option(..., "--workspace")):
    result = validate_readiness(workspace)
    console.print(f"ready: {result['ready']}")
    console.print(f"blocked_by: {result['blocked_by']}")
    console.print(f"warnings: {result['warnings']}")
    console.print(f"skipped_by_scope: {result.get('skipped_by_scope', [])}")
    console.print(f"recommended_next_action: {result['recommended_next_action']}")


@app.command("ai-context-preview")
def ai_context_preview_cmd(workspace: str = typer.Option(..., "--workspace"), opportunity_id: Optional[str] = typer.Option(None, "--opportunity-id")):
    path = write_ai_preview(workspace, opportunity_id)
    console.print(f"[green]AI context preview written without provider submission:[/] {path}")


@app.command("audit-log")
def audit_log_cmd(workspace: str = typer.Option(..., "--workspace")):
    events = read_events(workspace)
    if not events:
        console.print("No audit events recorded.")
        return
    table = Table("Time", "Type", "Command", "Result")
    for event in events:
        table.add_row(event.get("timestamp", ""), event.get("event_type", ""), event.get("command", ""), str(event.get("result", ""))[:80])
    console.print(table)


@app.command("list-artifacts")
def list_artifacts_cmd(workspace: str = typer.Option(..., "--workspace")):
    artifacts = list_artifacts(workspace)
    table = Table("ID", "Type", "Status", "Path", "Generated")
    for artifact in artifacts:
        table.add_row(artifact["id"], artifact["type"], artifact["status"], artifact["path"], artifact.get("generated_at", ""))
    console.print(table if artifacts else "No artifacts recorded yet.")


@app.command("mark-reviewed")
def mark_reviewed_cmd(workspace: str = typer.Option(..., "--workspace"), artifact: str = typer.Option(..., "--artifact"), reviewer: str = typer.Option("founder", "--reviewer")):
    updated = mark_reviewed(workspace, artifact, reviewer=reviewer)
    console.print(f"[green]Artifact marked founder-reviewed:[/] {updated['id']} ({updated['path']})")


@app.command("package-delivery")
def package_delivery_cmd(workspace: str = typer.Option(..., "--workspace")):
    path = package_delivery(workspace)
    console.print(f"[green]Delivery package created:[/] {path}")


@app.command("record-approval")
def record_approval_cmd(
    workspace: str = typer.Option(..., "--workspace"),
    approval_type: str = typer.Option(..., "--type", help="customer-delivery, remediation-planning, pr-diff-generation, or ai-use"),
    approved_by: str = typer.Option(..., "--approved-by"),
    note: str = typer.Option(..., "--note"),
    related_artifact: Optional[str] = typer.Option(None, "--related-artifact"),
    related_opportunity: Optional[str] = typer.Option(None, "--related-opportunity"),
):
    approval = record_approval(workspace, approval_type, approved_by, note, related_artifact, related_opportunity)
    console.print(f"[green]Approval recorded:[/] {approval['type']} by {approval['approved_by']}")


@app.command("delete-workspace")
def delete_workspace_cmd(workspace_name: str):
    handle = get_workspace(workspace_name)
    expected = f"DELETE {workspace_name}"
    console.print(f"This will permanently delete {handle.root}/.")
    confirmation = typer.prompt(f"Type {expected} to continue")
    if confirmation != expected:
        record_event(workspace_name, "failure", command="delete-workspace", params={"workspace": workspace_name}, result="confirmation_mismatch")
        console.print("[red]Confirmation did not match. Workspace was not deleted.[/]")
        raise typer.Exit(code=1)
    record_event(workspace_name, "command", command="delete-workspace", params={"workspace": workspace_name}, result="confirmed_delete")
    shutil.rmtree(handle.root)
    console.print(f"[green]Workspace deleted:[/] {handle.root}")
