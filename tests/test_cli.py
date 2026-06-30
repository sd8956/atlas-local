from typer.testing import CliRunner

from atlas_local.cli.app import app

runner = CliRunner()


def test_cli_init_workspace():
    result = runner.invoke(app, ["init-workspace", "demo"])
    assert result.exit_code == 0
    assert ".workspaces/demo" in result.output


def test_cli_pipeline_without_aws_collection(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.tf").write_text('resource "aws_instance" "web" {}\n', encoding="utf-8")
    assert runner.invoke(app, ["init-workspace", "demo"]).exit_code == 0
    assert runner.invoke(app, ["ingest-repo", "--workspace", "demo", "--path", str(repo)]).exit_code == 0
    assert runner.invoke(app, ["normalize", "--workspace", "demo"]).exit_code == 0
    assert runner.invoke(app, ["build-graph", "--workspace", "demo"]).exit_code == 0
    assert runner.invoke(app, ["analyze", "--workspace", "demo"]).exit_code == 0
    assert runner.invoke(app, ["ai-review", "--workspace", "demo"]).exit_code == 0
    assert runner.invoke(app, ["generate-readout", "--workspace", "demo"]).exit_code == 0
