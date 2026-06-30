# Atlas Local CLI Command Reference

Atlas Local is a local, operator-run CLI for evidence-first AWS remediation pilots. This reference documents every currently registered Typer command in `atlas_local/cli/app.py`.

## Quick path

```bash
atlas init-workspace <workspace>
atlas configure-workspace --workspace <workspace> --customer-alias <alias> --allowed-region us-east-1 --cost-explorer not-allowed --ai not-allowed
atlas collect-aws --workspace <workspace> --profile <readonly-profile> --regions us-east-1
atlas ingest-repo --workspace <workspace> --path /path/to/approved/repo
atlas normalize --workspace <workspace>
atlas build-graph --workspace <workspace>
atlas analyze --workspace <workspace> --no-ai
atlas ai-context-preview --workspace <workspace>
atlas generate-readout --workspace <workspace>
atlas generate-remediation-plan --workspace <workspace> --opportunity-id OPP-OWN-001
atlas record-approval --workspace <workspace> --type remediation-planning --approved-by founder --note "Approved advisory planning"
atlas record-approval --workspace <workspace> --type customer-delivery --approved-by founder --note "Approved reviewed package"
atlas list-artifacts --workspace <workspace>
atlas mark-reviewed --workspace <workspace> --artifact ART-xxxxxxxxxx
atlas validate-readiness --workspace <workspace>
atlas package-delivery --workspace <workspace>
atlas audit-log --workspace <workspace>
```

## Safety boundaries

| Boundary | CLI behavior |
|---|---|
| Local only | Workspaces are stored under `.workspaces/<workspace>/` on the operator machine. |
| Read-only AWS | `collect-aws` uses evidence collection only; Atlas does not mutate cloud resources. |
| No SaaS upload | Atlas does not upload raw AWS data or full repository source by default. |
| No auto-deploy/merge | Remediation plans are advisory; no PR, merge, deploy, or CI/CD bypass is performed. |
| Human gates | Delivery packaging requires reviewed artifacts and explicit `customer-delivery` approval. |
| AI boundedness | `ai-context-preview` writes local context only; `ai-review` skips when policy or provider config blocks it. |

## Workflow map

| Stage | Commands |
|---|---|
| Workspace setup | `init-workspace`, `configure-workspace`, `show-workspace` |
| Evidence intake | `collect-aws`, `ingest-repo`, `load-sample` |
| Local analysis | `normalize`, `build-graph`, `analyze` |
| AI review safety | `ai-context-preview`, `ai-review`, `analyze --no-ai` |
| Reporting and planning | `generate-readout`, `generate-remediation-plan` |
| Review, approval, delivery | `list-artifacts`, `mark-reviewed`, `record-approval`, `validate-readiness`, `package-delivery`, `audit-log` |
| Cleanup | `delete-workspace` |

## Workspace setup

### `atlas init-workspace <workspace_name>`

**Purpose:** Creates a local workspace and the standard directory layout under `.workspaces/<workspace_name>/`.

**When to use it:** Start every real customer pilot with this command before collecting evidence or ingesting repository context.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `workspace_name` | Yes | Workspace name argument. Slashes and `..` are sanitized for local path safety. | `acme-pilot` | Creates local customer-sensitive storage under `.workspaces/`. |

**Outputs/artifacts:** `workspace.json` plus directories for inputs, evidence, graph, opportunities, AI, reports, remediation, patches, audit, approvals, and delivery.

**Safety behavior/gates:** Does not contact AWS, read repositories, call AI, deploy, or mutate cloud resources.

**Example:**

```bash
atlas init-workspace acme-pilot
```

**Common failures/blockers:** Empty workspace name; filesystem permission problems.

### `atlas configure-workspace`

**Purpose:** Records customer alias, allowed AWS/repo scope, and Cost Explorer/AI policy in `workspace.json`.

**When to use it:** Before collecting customer evidence, especially when the operator needs explicit account, region, repo, AI, or Cost Explorer boundaries.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to configure; created if needed. | `acme-pilot` | Scope applies to later validation and some collection gates. |
| `--customer-alias` | Yes | Human-readable customer/workspace label. | `acme` | Avoid sensitive legal names if aliases are preferred. |
| `--allowed-account` | Optional | Allowed AWS account ID. Repeat the option or pass comma-separated values. | `123456789012` | `collect-aws` blocks evidence from non-allowed accounts when account identity is available. |
| `--allowed-region` | Optional | Allowed AWS region. Repeat the option or pass comma-separated values. | `us-east-1` | `collect-aws` blocks requested regions outside this list. |
| `--allowed-repo-path` | Optional | Approved local repository root path. Repeat the option or pass comma-separated values. | `/home/sd/customer/iac` | `ingest-repo` blocks paths outside configured roots. |
| `--cost-explorer` | Yes | Cost Explorer policy: `allowed` or `not-allowed`. | `not-allowed` | `not-allowed` is surfaced as skipped-by-scope in readiness. |
| `--ai` | Yes | AI policy: `allowed` or `not-allowed`. | `not-allowed` | `not-allowed` prevents provider submission and records skipped AI. |

**Outputs/artifacts:** Updates `.workspaces/<workspace>/workspace.json`; appends audit event to `audit/audit-log.jsonl`.

**Safety behavior/gates:** Validates policy values. Later commands use the scope to block disallowed AWS regions/accounts and repo paths.

**Example:**

```bash
atlas configure-workspace --workspace acme-pilot --customer-alias acme --allowed-account 123456789012 --allowed-region us-east-1 --allowed-repo-path /home/sd/acme/iac --cost-explorer not-allowed --ai not-allowed
```

**Common failures/blockers:** `--cost-explorer` or `--ai` not set to `allowed`/`not-allowed`; invalid local paths later blocked during ingestion.

### `atlas show-workspace --workspace <name>`

**Purpose:** Prints the configured workspace scope as a table.

**When to use it:** Before collection, AI review, or customer delivery to confirm the current safety envelope.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to inspect. | `acme-pilot` | Read-only command. |

**Outputs/artifacts:** Console table only; no workspace files modified.

**Safety behavior/gates:** Fails if the workspace does not exist.

**Example:**

```bash
atlas show-workspace --workspace acme-pilot
```

**Common failures/blockers:** Workspace missing; run `atlas init-workspace <name>` first.

## Evidence intake

### `atlas collect-aws`

**Purpose:** Collects read-only AWS evidence for configured regions using a local AWS profile.

**When to use it:** After workspace scope is configured and the operator has a read-only AWS profile for the approved account/regions.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace receiving raw AWS evidence. | `acme-pilot` | Writes customer-sensitive JSON under `.workspaces/`. |
| `--profile` | Yes | Local AWS profile name passed to `boto3.Session`. | `acme-readonly` | Use read-only credentials only. |
| `--regions` | Yes | Comma-separated AWS regions to collect. | `us-east-1,us-west-2` | Blocked when requested regions are outside configured scope. |

**Outputs/artifacts:** Raw service payloads in `evidence/raw/aws/*.json`; manifest in `evidence/raw/aws/manifest.json`.

**Safety behavior/gates:** Blocks disallowed regions and disallowed accounts when identity is available; records scope blocks/warnings in audit. Collector-level AWS permission errors are captured in payload errors instead of authorizing mutation.

**Example:**

```bash
atlas collect-aws --workspace acme-pilot --profile acme-readonly --regions us-east-1,us-west-2
```

**Common failures/blockers:** Workspace missing; AWS profile missing; STS/account identity unavailable warning; requested region/account outside configured scope; local AWS permission/network errors.

### `atlas ingest-repo`

**Purpose:** Summarizes approved local repository files into repository observations for IaC/linkage analysis.

**When to use it:** After the customer approves local repository scope for CDK, Terraform, CloudFormation, or related config evidence.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace receiving repository observations. | `acme-pilot` | Writes snippets and declarations, not a full repo copy. |
| `--path` | Yes | Local repository root to scan. | `/home/sd/acme/iac` | Blocked if outside configured `--allowed-repo-path` scope. |

**Outputs/artifacts:** `evidence/raw/repository/observations.json` containing file paths, hashes, short snippets, declarations, and detected kind.

**Safety behavior/gates:** Scans selected file extensions and CDK indicator files only; stores up to short snippets/declarations; blocks paths outside configured repo scope.

**Example:**

```bash
atlas ingest-repo --workspace acme-pilot --path /home/sd/acme/iac
```

**Common failures/blockers:** Workspace missing; path does not exist; path outside allowed scope; unreadable files.

### `atlas load-sample --workspace <name>`

**Purpose:** Loads bundled sample AWS evidence and sample repository observations into a workspace.

**When to use it:** For a local demo without customer credentials, external network access, or a real repository.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Demo workspace to create or refresh with sample data. | `demo` | Uses bundled local sample data only. |

**Outputs/artifacts:** Sample files under `evidence/raw/aws/`; repository observations under `evidence/raw/repository/observations.json`; audit event.

**Safety behavior/gates:** Does not call AWS or AI and does not need customer credentials.

**Example:**

```bash
atlas load-sample --workspace demo
```

**Common failures/blockers:** Missing bundled sample data; filesystem permission problems.

## Local analysis

### `atlas normalize --workspace <name>`

**Purpose:** Converts raw AWS/repository evidence into normalized AWS resources, IaC entities, repositories, and relationships.

**When to use it:** After `collect-aws`, `ingest-repo`, or `load-sample`, before graph building and analysis.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace with raw evidence to normalize. | `acme-pilot` | Local file processing only. |

**Outputs/artifacts:** `evidence/normalized/normalized.json`.

**Safety behavior/gates:** Does not contact AWS, AI, or repositories; reads local workspace files only.

**Example:**

```bash
atlas normalize --workspace acme-pilot
```

**Common failures/blockers:** Workspace missing; no raw evidence means output may have empty resources/entities.

### `atlas build-graph --workspace <name>`

**Purpose:** Builds the local Engineering Graph from normalized resources and IaC entities.

**When to use it:** After `normalize`, before deterministic analysis or AI context preview.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace with normalized evidence. | `acme-pilot` | Local file processing only. |

**Outputs/artifacts:** `graph/engineering-graph.json` containing nodes, edges, and relationship types.

**Safety behavior/gates:** Does not mutate cloud resources or repository files.

**Example:**

```bash
atlas build-graph --workspace acme-pilot
```

**Common failures/blockers:** Workspace missing; missing normalized evidence produces an empty or limited graph.

### `atlas analyze`

**Purpose:** Runs deterministic analyzers and writes Engineering Opportunities.

**When to use it:** After `build-graph`; use `--no-ai` for the safest first pass.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to analyze. | `acme-pilot` | Reads local normalized evidence and graph only. |
| `--no-ai` | Optional | Forces deterministic-only analysis and writes a skipped AI artifact. | `--no-ai` | Guarantees no AI provider call for this command. |

**Outputs/artifacts:** `opportunities/opportunities.json`; with `--no-ai`, also `ai/ai-review.json`; audit event.

**Safety behavior/gates:** Does not mutate AWS, repos, deploy, merge, or call AI when `--no-ai` is set. Opportunities include assumptions and confidence limits.

**Example:**

```bash
atlas analyze --workspace acme-pilot --no-ai
```

**Common failures/blockers:** Workspace missing; no normalized resources/graph can produce no opportunities.

## AI review safety

### `atlas ai-context-preview`

**Purpose:** Writes the exact bounded context that would be used for AI review without submitting it to a provider.

**When to use it:** Before any provider-backed `ai-review`, and when reviewing whether a single opportunity has enough safe context.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace whose bounded context should be previewed. | `acme-pilot` | Preview is local-only; no provider submission. |
| `--opportunity-id` | Optional | Limits opportunities and graph neighborhood to one opportunity. | `OPP-SEC-002` | Use for risky/sensitive findings to reduce context. |

**Outputs/artifacts:** `ai/context-preview-workspace.json` or `ai/context-preview-<opportunity-id>.json`; artifact metadata; audit event.

**Safety behavior/gates:** Includes normalized evidence, graph, and opportunities only; excludes raw repository source and raw AWS delivery payloads by default; explicitly states no provider submission.

**Example:**

```bash
atlas ai-context-preview --workspace acme-pilot --opportunity-id OPP-SEC-002
```

**Common failures/blockers:** Workspace missing; missing normalized evidence/graph/opportunities results in sparse preview context.

### `atlas ai-review`

**Purpose:** Runs provider-backed AI review when configured, or writes a skipped AI artifact when policy/provider config prevents it.

**When to use it:** Only after previewing context and confirming workspace AI policy allows AI use.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to review. | `acme-pilot` | AI reads bounded local context only. |
| `--provider` | Optional | Provider adapter name. Current scaffold has no hardcoded provider. | `openai` | Without `ATLAS_AI_API_KEY` and adapter support, review is skipped. |

**Outputs/artifacts:** `ai/ai-review.json`; artifact metadata; audit event.

**Safety behavior/gates:** If workspace AI policy is `not-allowed`, writes `ai-review-skipped-by-scope` and makes no provider call. If no provider is configured, writes skipped artifact. AI output is draft reasoning, never approval.

**Example:**

```bash
atlas ai-review --workspace acme-pilot --provider openai
```

**Common failures/blockers:** Workspace missing; AI policy `not-allowed`; no `ATLAS_AI_API_KEY`; no provider adapter configured in the scaffold.

## Reporting and planning

### `atlas generate-readout --workspace <name>`

**Purpose:** Generates customer-reviewable Markdown reports from Engineering Opportunities.

**When to use it:** After `analyze`, before artifact review and delivery packaging.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to report on. | `acme-pilot` | Reports remain draft until reviewed. |

**Outputs/artifacts:** `reports/pilot-readout.md`, `reports/engineering-opportunities.md`; artifact metadata; audit event.

**Safety behavior/gates:** Generated reports say human review is required and include what Atlas did not do.

**Example:**

```bash
atlas generate-readout --workspace acme-pilot
```

**Common failures/blockers:** Workspace missing; no opportunities results in empty/no-opportunity report content.

### `atlas generate-remediation-plan`

**Purpose:** Creates an advisory remediation plan for one opportunity.

**When to use it:** After a human has selected an opportunity worth advisory planning.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace containing opportunities. | `acme-pilot` | Plan is advisory only. |
| `--opportunity-id` | Yes | Opportunity ID from `opportunities/opportunities.json` or reports. | `OPP-COST-003` | Does not generate PR/diff or mutate cloud resources. |

**Outputs/artifacts:** `remediation/<opportunity-id>.json`, `remediation/<opportunity-id>.md`; artifact metadata; audit event.

**Safety behavior/gates:** Plan states no cloud mutation, no code generation, and no PR/diff without explicit human approval.

**Example:**

```bash
atlas generate-remediation-plan --workspace acme-pilot --opportunity-id OPP-COST-003
```

**Common failures/blockers:** Workspace missing; opportunity ID not found.

## Review, approval, delivery, and audit

### `atlas validate-readiness --workspace <name>`

**Purpose:** Checks whether the workspace is safe enough for the next delivery step.

**When to use it:** Before customer delivery, after generating/reviewing artifacts, and after recording required approvals.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to validate. | `acme-pilot` | Readiness can block delivery on missing review/approvals/scope. |

**Outputs/artifacts:** Console fields: `ready`, `blocked_by`, `warnings`, `skipped_by_scope`, `recommended_next_action`; audit events.

**Safety behavior/gates:** Blocks or warns on missing AWS/normalized evidence, missing opportunities, low confidence, scope mismatches, skipped/incomplete AI, draft artifacts, missing customer-delivery approval, missing remediation-planning approval, missing AI-use approval when applicable, and unsupported PR/diff paths.

**Example:**

```bash
atlas validate-readiness --workspace acme-pilot
```

**Common failures/blockers:** Missing evidence; draft artifacts; missing reviewed/customer-ready artifacts; missing `customer-delivery`, `remediation-planning`, or `ai-use` approvals; disallowed account/region evidence.

### `atlas list-artifacts --workspace <name>`

**Purpose:** Lists registered reports, plans, AI outputs, previews, and delivery packages with review status.

**When to use it:** Before `mark-reviewed`, readiness validation, or package delivery.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace whose artifact metadata should be listed. | `acme-pilot` | Read-only command. |

**Outputs/artifacts:** Console table with ID, type, status, path, and generated timestamp.

**Safety behavior/gates:** Does not change artifact state.

**Example:**

```bash
atlas list-artifacts --workspace acme-pilot
```

**Common failures/blockers:** Workspace missing; no artifacts registered yet.

### `atlas mark-reviewed`

**Purpose:** Marks one artifact as founder-reviewed and records reviewer metadata.

**When to use it:** After the operator has manually reviewed a draft report, plan, or AI artifact and accepts it for customer preparation.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace containing the artifact. | `acme-pilot` | Human review action; do not automate without actual review. |
| `--artifact` | Yes | Artifact ID from `list-artifacts`. | `ART-1a2b3c4d5e` | Marks only metadata, not content correctness. |
| `--reviewer` | Optional | Reviewer name recorded in metadata; defaults to `founder`. | `founder` | Use accountable human/operator identity. |

**Outputs/artifacts:** Updates `artifacts/metadata.json` and legacy `audit/artifacts.json`; audit review event.

**Safety behavior/gates:** Changes status to `founder-reviewed`; package delivery still requires required artifacts and explicit customer-delivery approval.

**Example:**

```bash
atlas mark-reviewed --workspace acme-pilot --artifact ART-1a2b3c4d5e --reviewer founder
```

**Common failures/blockers:** Artifact ID not found; workspace missing.

### `atlas record-approval`

**Purpose:** Records explicit human approval for delivery, remediation planning, PR/diff generation, or AI use.

**When to use it:** Before packaging customer delivery or whenever a safety gate requires documented human approval.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace receiving the approval record. | `acme-pilot` | Approval becomes part of local audit/delivery trace. |
| `--type` | Yes | Approval type: `customer-delivery`, `remediation-planning`, `pr-diff-generation`, or `ai-use`. | `customer-delivery` | Invalid approval types are rejected. |
| `--approved-by` | Yes | Human/operator who approved. | `founder` | Use accountable identity, not an automated placeholder. |
| `--note` | Yes | Reason, scope, or context for approval. | `Approved reviewed package for customer call` | Keep enough context for auditability. |
| `--related-artifact` | Optional | Artifact ID related to the approval. | `ART-1a2b3c4d5e` | Helps trace approval to a concrete deliverable. |
| `--related-opportunity` | Optional | Opportunity ID related to the approval. | `OPP-COST-003` | Helps trace approval to a finding/remediation path. |

**Outputs/artifacts:** Appends to `approvals/approvals.json`; audit approval event.

**Safety behavior/gates:** Readiness and packaging check these records for delivery/remediation/AI gates.

**Example:**

```bash
atlas record-approval --workspace acme-pilot --type customer-delivery --approved-by founder --note "Approved reviewed artifacts for customer delivery" --related-artifact ART-1a2b3c4d5e
```

**Common failures/blockers:** Invalid `--type`; workspace missing; vague notes that are not useful for audit.

### `atlas package-delivery --workspace <name>`

**Purpose:** Builds a customer-facing delivery package from reviewed reports/plans and approval metadata.

**When to use it:** Only after required artifacts are founder-reviewed/customer-ready and customer-delivery approval is recorded.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace to package. | `acme-pilot` | Excludes raw AWS evidence and full repository source by default. |

**Outputs/artifacts:** `delivery/<workspace>-atlas-pilot/` containing `README.md`, copied report Markdown, `remediation-plans/`, `evidence-summary.md`, `next-steps.md`, `workspace-scope.json`, `approvals.json`, and `artifact-manifest.json`; registers delivery package; audit delivery event.

**Safety behavior/gates:** Blocks if no report/remediation artifacts exist, if required report/remediation artifacts are not reviewed, or if `customer-delivery` approval is missing.

**Example:**

```bash
atlas package-delivery --workspace acme-pilot
```

**Common failures/blockers:** No generated reports/plans; unreviewed required artifacts; missing `customer-delivery` approval; filesystem permission problems.

### `atlas audit-log --workspace <name>`

**Purpose:** Displays recorded workspace audit events in a concise table.

**When to use it:** Before customer delivery, after failures, or when reconstructing what Atlas did.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Yes | Workspace whose audit log should be displayed. | `acme-pilot` | Read-only view of local audit file. |

**Outputs/artifacts:** Console table with time, event type, command, and result.

**Safety behavior/gates:** Does not modify the audit log.

**Example:**

```bash
atlas audit-log --workspace acme-pilot
```

**Common failures/blockers:** Workspace missing; no audit events recorded yet.

## Demo automation

### `atlas demo --workspace <name>`

**Purpose:** Runs the sample demo workflow end to end for a local workspace.

**When to use it:** To produce demo artifacts quickly without customer credentials or external AWS access.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `--workspace` | Optional | Demo workspace name; defaults to `demo`. | `demo` | Uses bundled sample data, not customer credentials. |

**Outputs/artifacts:** Sample evidence, `evidence/normalized/normalized.json`, `graph/engineering-graph.json`, `opportunities/opportunities.json`, `ai/ai-review.json`, reports, and one remediation plan when an opportunity exists; audit event.

**Safety behavior/gates:** `run_demo` calls deterministic analysis with `no_ai=True`, then `ai-review`; if no provider is configured or AI scope disallows it, AI is skipped. It does not mutate AWS, deploy, merge, or generate PR/diffs.

**Example:**

```bash
atlas demo --workspace demo
```

**Common failures/blockers:** Missing sample data; report/plan generation limited if no opportunities are produced; AI review skipped because the scaffold has no configured provider.

## Cleanup

### `atlas delete-workspace <workspace_name>`

**Purpose:** Permanently deletes a local workspace directory.

**When to use it:** After customer-sensitive local data is no longer needed and retention requirements allow deletion.

| Name | Required | Meaning | Example value | Safety note |
|---|---:|---|---|---|
| `workspace_name` | Yes | Workspace name argument to delete. | `acme-pilot` | Destructive. Requires exact confirmation `DELETE <workspace_name>`. |

**Outputs/artifacts:** Removes `.workspaces/<workspace_name>/`; records a final audit event before removal when confirmation succeeds or a failure event when confirmation mismatches.

**Safety behavior/gates:** Prompts: `Type DELETE <workspace_name> to continue`. Any mismatch exits without deletion.

**Example:**

```bash
atlas delete-workspace acme-pilot
```

Then type:

```text
DELETE acme-pilot
```

**Common failures/blockers:** Workspace missing; confirmation mismatch; filesystem permission problems.

## Command and parameter checklist

Use this checklist when updating the CLI so docs do not drift.

| Command | Parameters documented |
|---|---|
| `init-workspace` | `workspace_name` |
| `configure-workspace` | `--workspace`, `--customer-alias`, `--allowed-account`, `--allowed-region`, `--allowed-repo-path`, `--cost-explorer`, `--ai` |
| `show-workspace` | `--workspace` |
| `collect-aws` | `--workspace`, `--profile`, `--regions` |
| `ingest-repo` | `--workspace`, `--path` |
| `normalize` | `--workspace` |
| `build-graph` | `--workspace` |
| `analyze` | `--workspace`, `--no-ai` |
| `ai-review` | `--workspace`, `--provider` |
| `ai-context-preview` | `--workspace`, `--opportunity-id` |
| `generate-readout` | `--workspace` |
| `generate-remediation-plan` | `--workspace`, `--opportunity-id` |
| `validate-readiness` | `--workspace` |
| `list-artifacts` | `--workspace` |
| `mark-reviewed` | `--workspace`, `--artifact`, `--reviewer` |
| `record-approval` | `--workspace`, `--type`, `--approved-by`, `--note`, `--related-artifact`, `--related-opportunity` |
| `package-delivery` | `--workspace` |
| `audit-log` | `--workspace` |
| `load-sample` | `--workspace` |
| `demo` | `--workspace` |
| `delete-workspace` | `workspace_name` |
