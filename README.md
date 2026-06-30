# Atlas Local

Atlas Local is an **operator-run local tool** for AWS Remediation Pilots. It collects read-only evidence, normalizes it, builds an Engineering Graph, runs deterministic analyzers, and prepares evidence-bounded pilot artifacts.

It is built for a founder/operator delivering paid remediation pilots, not for autonomous production changes.

## What Atlas Local is not

Atlas Local is not SaaS, not an agent that changes cloud infrastructure, and not a CI/CD bypass. It does not deploy, merge, mutate AWS, upload repository content, or generate remediation diffs without human approval.

## Safety boundaries

| Boundary | MVP behavior |
|---|---|
| AWS access | Read-only collection only. Collectors use describe/list/get-style APIs. |
| Cloud changes | No direct mutation. |
| Customer delivery | Human review required before sharing. |
| Remediation | Human approval required before planning; PR/diff generation is blocked in this scaffold. |
| AI | AI can only reason over local normalized evidence, graph, and opportunities. Unsupported claims must be marked. |
| Isolation | Each customer/workspace lives under `.workspaces/<name>/`. |

> Local data warning: `.workspaces/` can contain customer metadata, AWS inventory, repo snippets, and analysis artifacts. Treat it as customer-sensitive and do not commit it.

## Setup

Requires Python 3.14+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Quick path

Use `--no-ai` first for a fully deterministic local run, then preview the bounded AI context before any provider-backed review.

```bash
atlas init-workspace <workspace_name>
atlas configure-workspace --workspace <name> --customer-alias <alias> --allowed-region us-east-1 --cost-explorer not-allowed --ai not-allowed
atlas collect-aws --workspace <name> --profile <aws_profile> --regions us-east-1,us-west-2
atlas ingest-repo --workspace <name> --path <repo_path>
atlas normalize --workspace <name>
atlas build-graph --workspace <name>
atlas analyze --workspace <name> --no-ai
atlas ai-context-preview --workspace <name>
atlas generate-readout --workspace <name>
atlas generate-remediation-plan --workspace <name> --opportunity-id <id>
atlas record-approval --workspace <name> --type remediation-planning --approved-by <operator> --note "Approved advisory planning"
atlas list-artifacts --workspace <name>
atlas mark-reviewed --workspace <name> --artifact <artifact_id>
atlas record-approval --workspace <name> --type customer-delivery --approved-by <operator> --note "Approved reviewed package"
atlas validate-readiness --workspace <name>
atlas package-delivery --workspace <name>
```

For every command, option, artifact, safety gate, and common blocker, see [`docs/commands.md`](docs/commands.md).

For a step-by-step real customer execution checklist, see [`docs/runbooks/first-customer-pilot.md`](docs/runbooks/first-customer-pilot.md).

## Implemented command groups

| Group | Commands | What they do |
|---|---|---|
| Workspace scope | `init-workspace`, `configure-workspace`, `show-workspace`, `delete-workspace` | Create, constrain, inspect, and strongly confirm deletion of local workspace data. |
| Evidence | `collect-aws`, `ingest-repo`, `load-sample` | Collect read-only AWS evidence, summarize approved local repo context, or load local demo data. |
| Processing | `normalize`, `build-graph`, `analyze` | Convert evidence into normalized resources, graph relationships, and Engineering Opportunities. |
| AI safety | `ai-context-preview`, `ai-review`, `analyze --no-ai` | Preview bounded context, run or skip provider-backed review, and support deterministic no-AI operation. |
| Reports and plans | `generate-readout`, `generate-remediation-plan` | Write pilot readouts, opportunity reports, and advisory remediation plans. |
| Review and delivery | `validate-readiness`, `list-artifacts`, `mark-reviewed`, `record-approval`, `package-delivery`, `audit-log` | Gate delivery on human review, explicit approvals, auditability, and customer-safe packaging. |

## Local demo

```bash
atlas load-sample --workspace <name>
atlas demo --workspace <name>
```

`demo` loads sample evidence, normalizes it, builds the graph, runs deterministic analysis, writes/skips AI review as configured, generates reports, and creates one advisory remediation plan when an opportunity exists.

See [`docs/mvp-pilot-readiness-plan.md`](docs/mvp-pilot-readiness-plan.md) for the pilot-readiness plan and [`docs/commands.md`](docs/commands.md) for the exact CLI reference.

You can also invoke the module path in tests or local runs:

```bash
python -m atlas_local.cli init-workspace demo
```

## Workflow

1. Create a workspace.
2. Collect AWS evidence read-only and/or ingest repository evidence.
3. Normalize evidence into resources, IaC entities, and relationships.
4. Build the local Engineering Graph.
5. Run deterministic analyzers to produce Engineering Opportunities.
6. Run without AI first, then preview bounded AI context before any provider-backed review.
7. Generate Markdown reports and, after approval, an advisory remediation plan.
8. Validate readiness, mark founder-reviewed artifacts, and package customer delivery.

## Workspace layout

Each workspace is stored under `.workspaces/<workspace>/`:

```text
workspace.json
inputs/
evidence/raw/
evidence/normalized/
repo/
graph/
opportunities/
ai/
reports/
remediation/
patches/
audit/
approvals/
delivery/
```

`workspace.json` records the workspace name, creation time, customer alias, notes, safety constraints, allowed AWS accounts/regions/repo paths, analysis depth, AI usage settings, and human review status.

## AWS collection scope

The scaffold includes broad collector coverage with shallow read-only calls:

- Account identity
- EC2 instances, EBS volumes, AMIs/snapshots, VPCs, subnets, route tables, NAT gateways, internet gateways, security groups
- RDS instances/clusters
- Lambda, API Gateway, ECS, ECR, ELB/ALB/NLB
- IAM roles and local policies metadata
- S3 buckets
- CloudWatch alarms and log groups
- DynamoDB tables
- EventBridge rules
- SQS queues and SNS topics
- CloudFormation stacks
- Cost Explorer when permissions are available

Missing permissions are recorded as errors in raw evidence instead of failing the whole run.

## AI analysis

The AI layer is provider-abstracted. No provider is hardcoded. Without `ATLAS_AI_API_KEY` and a configured adapter, Atlas must skip gracefully and mark AI-backed assumptions instead of blocking deterministic analysis.

When enabled later, AI must use only bounded context from:

- `evidence/normalized/normalized.json`
- `graph/engineering-graph.json`
- `opportunities/opportunities.json`

Use `atlas ai-context-preview --workspace <name>` before any provider submission. Use `--opportunity-id <id>` to preview only one opportunity's context.

## Demo delivery package

```bash
atlas demo --workspace demo
```

The demo loads sample AWS evidence and sample CDK/Terraform repository observations, runs the local workflow, and generates Engineering Opportunities, a pilot readout, and one remediation plan.

After founder review, package the demo delivery with:

```bash
atlas list-artifacts --workspace demo
atlas mark-reviewed --workspace demo --artifact <artifact_id>
atlas record-approval --workspace demo --type customer-delivery --approved-by founder --note "Approved reviewed demo package"
atlas validate-readiness --workspace demo
atlas package-delivery --workspace demo
```

## First paid pilot readiness

Before customer delivery, run:

```bash
atlas list-artifacts --workspace <name>
atlas mark-reviewed --workspace <name> --artifact <artifact_id>
atlas record-approval --workspace <name> --type customer-delivery --approved-by <operator> --note "Approved reviewed package"
atlas validate-readiness --workspace <name>
atlas package-delivery --workspace <name>
```

Readiness must block or warn on missing AWS/repo/Cost Explorer evidence, failed collectors, low confidence, missing human review, skipped AI where AI-backed claims are expected, sensitive findings, missing approvals, unsupported remediation paths, and unsafe delivery.

## Deterministic analyzers in this scaffold

The MVP starts with useful, low-noise opportunities:

- Missing owner tags
- Broad public security groups
- Unattached EBS volumes
- Stopped EC2 instances
- NAT Gateway cost review
- Missing IaC linkage when AWS resources exist but no IaC entities were ingested

These are intentionally advisory. Each opportunity includes evidence, confidence, rationale, next action, why it might be wrong, and confidence-improvement guidance.
