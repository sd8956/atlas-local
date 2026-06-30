# Atlas Local MVP Pilot Readiness Plan

Atlas Local should be safe enough to guide a first paid pilot before it becomes broader SaaS. This plan keeps the tool local and operator-run while adding the minimum gates, artifacts, audit trail, and delivery package needed for real customer work.

## Quick Path

### Local demo

```bash
atlas load-sample --workspace demo
atlas demo
```

Expected demo output:

| Output | Location |
|---|---|
| Sample AWS and CDK/Terraform evidence | `.workspaces/demo/evidence/` |
| Engineering Opportunities | `.workspaces/demo/opportunities/` and reports |
| Pilot readout | `.workspaces/demo/reports/pilot-readout.md` |
| One remediation plan | `.workspaces/demo/remediation/` |

Optional packaging after review:

```bash
atlas validate-readiness --workspace demo
atlas list-artifacts --workspace demo
atlas mark-reviewed --workspace demo --artifact <artifact-id>
atlas record-approval --workspace demo --type customer-delivery --approved-by founder --note "Approved reviewed demo package"
atlas package-delivery --workspace demo
```

### First real paid pilot

```bash
atlas init-workspace <customer-workspace>
atlas configure-workspace --workspace <customer-workspace> --customer-alias <alias> --allowed-region <region> --cost-explorer <cost-policy> --ai <ai-policy>
atlas collect-aws --workspace <customer-workspace> --profile <readonly-profile> --regions <region-list>
atlas ingest-repo --workspace <customer-workspace> --path <approved-cdk-or-terraform-repo>
atlas normalize --workspace <customer-workspace>
atlas build-graph --workspace <customer-workspace>
atlas analyze --workspace <customer-workspace> --no-ai
atlas ai-context-preview --workspace <customer-workspace>
atlas analyze --workspace <customer-workspace>
atlas generate-readout --workspace <customer-workspace>
atlas generate-remediation-plan --workspace <customer-workspace> --opportunity-id <opportunity-id>
atlas record-approval --workspace <customer-workspace> --type remediation-planning --approved-by <operator> --note "Approved advisory planning"
atlas list-artifacts --workspace <customer-workspace>
atlas mark-reviewed --workspace <customer-workspace> --artifact <artifact-id>
atlas record-approval --workspace <customer-workspace> --type customer-delivery --approved-by <operator> --note "Approved reviewed package"
atlas validate-readiness --workspace <customer-workspace>
atlas package-delivery --workspace <customer-workspace>
```

Use `atlas audit-log --workspace <customer-workspace>` before delivery to review what Atlas did and did not do.

## Review Intent

Review this plan for pilot safety, not feature breadth. The implementation should prove one operator-run workflow from scoped evidence to customer-ready package while preserving human control.

| Review area | Question |
|---|---|
| Safety | Are mutation, deploy, merge, CI bypass, raw evidence exposure, and unsafe AI submission blocked or warned? |
| Pilot usefulness | Can a founder run a demo and a real paid pilot without hidden manual steps? |
| Evidence quality | Do opportunities and readouts show source, confidence, missing data, and assumptions? |
| Delivery quality | Can a customer receive a focused package without raw AWS or full repository contents by default? |
| Auditability | Can the operator reconstruct commands, artifacts, approvals, failures, and delivery events? |

## Scope

### In scope

| Capability | Required MVP behavior |
|---|---|
| Demo mode | Load sample AWS evidence and sample CDK/Terraform repo observations, run the workflow, and generate Engineering Opportunities, pilot readout, and one remediation plan. |
| Readiness validation | Report `ready: yes/no`, blockers, warnings, and recommended next action before internal review, delivery, remediation planning, or PR/diff generation. |
| No-AI operation | Atlas must work without AI, mark assumptions clearly, and skip gracefully without an API key. |
| AI context preview | Show bounded context before any provider submission, optionally scoped to one opportunity. |
| Local audit log | Record workspace-local command, artifact, failure, AI, report, remediation, review, and delivery events. |
| Human review statuses | Track artifact state from draft through founder review, customer readiness, delivery, and supersession. |
| Delivery package | Produce a customer-safe package with summaries, references, disclaimers, next steps, and no raw AWS or full repo payloads by default. |
| Workspace deletion | Provide strong confirmation before deleting workspace-local customer data. |
| Test coverage | Cover demo workflow, readiness gates, no-AI path, AI preview, audit log, review status changes, delivery package, deletion confirmation, and required report sections. |

### Out of scope

| Not included | Reason |
|---|---|
| SaaS onboarding, billing, hosted dashboard, or tenant admin | First paid pilots are founder-operated. |
| Cloud mutation | Atlas collects read-only AWS evidence only. |
| Auto-merge, auto-deploy, or CI/CD control | Customers keep implementation authority. |
| Autonomous PR/diff generation | Planning and PR/diff output require approval and review gates. |
| Raw evidence delivery by default | Customer packages should include summaries and references unless explicitly approved. |
| Multi-cloud support | The first sellable slice is AWS-first with CDK or Terraform. |
| Compliance certification claims | Atlas provides traceable artifacts, not certification. |

## Implemented Pilot-Readiness Commands

These commands are implemented in the current scaffold. For the full command reference, including every parameter and common blocker, see [`commands.md`](commands.md).

| Command | Purpose | Pilot safety requirement |
|---|---|---|
| `atlas load-sample --workspace <name>` | Create or refresh sample evidence and repo observations for a demo workspace. | Must not require AWS, customer credentials, or external network access. |
| `atlas demo` | Run the sample workflow end to end. | Must generate opportunities, readout, and one remediation plan from sample data only. |
| `atlas validate-readiness --workspace <name>` | Check whether a workspace is ready for review, delivery, remediation planning, or PR/diff generation. | Must return ready yes/no, blocked by, warnings, and recommended next action. |
| `atlas analyze --workspace <name> --no-ai` | Run deterministic analysis without provider submission. | Must produce useful results and mark assumptions caused by skipped AI. |
| `atlas ai-context-preview --workspace <name>` | Preview the exact bounded context that would be sent to AI. | Must not submit to a provider. |
| `atlas ai-context-preview --workspace <name> --opportunity-id <id>` | Preview opportunity-scoped AI context. | Must include only relevant evidence, graph neighborhood, assumptions, and prompt purpose. |
| `atlas audit-log --workspace <name>` | Show local workspace audit events. | Must make review and delivery traceable. |
| `atlas list-artifacts --workspace <name>` | List reports, plans, AI outputs, delivery packages, diffs, and review states. | Must show artifact ID, type, status, path, generated time, and supersession when relevant. |
| `atlas mark-reviewed --workspace <name> --artifact <artifact_id>` | Advance a draft artifact after founder review. | Must record reviewer, timestamp, artifact ID, and status transition in audit log. |
| `atlas record-approval --workspace <name> --type <approval-type> --approved-by <operator> --note <note>` | Record explicit human approval for customer delivery, remediation planning, PR/diff generation, or AI use. | Must create an auditable approval trail before gated delivery/planning actions. |
| `atlas package-delivery --workspace <name>` | Build customer-facing package. | Must block or warn when artifacts are not reviewed and must exclude raw AWS/full repo by default. |
| `atlas delete-workspace <name>` | Delete local workspace data. | Must require strong confirmation that includes the workspace name. |

## Readiness Validation

`atlas validate-readiness --workspace <name>` is the operator's safety gate before sharing or generating customer-facing work.

### Output contract

| Field | Meaning |
|---|---|
| `ready` | `yes` only when the requested workflow can proceed safely. |
| `blocked_by` | Hard blockers that prevent the next action. |
| `warnings` | Non-blocking issues the operator must understand. |
| `recommended_next_action` | One concrete next command or manual review step. |

### Checks

| Area | Block or warn when |
|---|---|
| Internal review | Generated reports, remediation plans, AI outputs, or delivery artifacts are still draft. |
| Customer delivery | No founder-reviewed/customer-ready artifact exists, or delivery override is requested. |
| Remediation planning | No explicit approval, opportunity is low confidence, or evidence is incomplete. |
| PR/diff generation | Missing plan approval, missing PR/diff approval, unsupported IaC target, weak repo linkage, sensitive change, or low confidence. |
| AWS evidence | Missing AWS evidence, stale evidence, failed collectors, missing account/region scope, or incomplete Cost Explorer data when cost claims depend on it. |
| Repository evidence | Missing approved CDK/Terraform repo context, weak IaC linkage, or unsupported remediation path. |
| AI | AI skipped/not run where AI-backed claims are expected, no API key, failed provider call, or missing context preview. |
| Sensitive findings | IAM, networking, encryption, retention, deletion, public exposure, or production-sensitive changes require explicit warning and stronger review. |
| Approvals | Missing planning approval, PR/diff approval, founder review, or customer delivery approval. |

## AI Safety And No-AI Mode

Atlas must be useful without AI and safer with AI.

| Requirement | Behavior |
|---|---|
| No API key | Skip AI gracefully and write an explicit skipped artifact. |
| `--no-ai` | Produce deterministic opportunities and reports without provider calls. |
| Assumptions | Mark assumptions and confidence limits caused by missing AI, missing graph links, or missing evidence. |
| Preview first | `atlas ai-context-preview` shows the bounded context before any provider submission. |
| Bounded context | AI receives only normalized evidence, Engineering Graph neighborhood, selected opportunity, relevant memory/constraints, and the exact task. |
| Optional opportunity scope | `--opportunity-id <id>` narrows context for high-value or risky opportunities. |
| No AI authority | AI output is draft reasoning, never approval, customer delivery, PR generation, merge, deploy, or graph truth by itself. |

## Audit Log

Each workspace needs a local audit log, for example `.workspaces/<name>/audit/audit-log.jsonl` plus a readable CLI view.

| Event type | Minimum fields |
|---|---|
| Command | Timestamp, command, params, workspace, operator if known, result. |
| File change | Files created/updated/deleted by Atlas, artifact IDs, content hashes when practical. |
| Failure | Failed collector, failed AI call, failed validation, exception class/message, affected artifact. |
| AI | Preview generated, provider skipped/run, model/provider if known, bounded context reference, output artifact. |
| Report | Report generated, status, source projection timestamps, warnings. |
| Remediation | Plan generated, linked opportunity, approvals required, unsupported path warnings. |
| Review | Artifact status transition, reviewer, timestamp, reason/comment when provided. |
| Delivery | Package generated, included artifacts, excluded raw evidence/repo data, override warning if used. |

## Artifact Review States

Reports, plans, AI review outputs, delivery packages, and PR/diff artifacts must have explicit review state.

| Status | Meaning |
|---|---|
| `draft` | Generated but not founder-reviewed. |
| `founder-reviewed` | Operator reviewed and accepted it for customer preparation. |
| `customer-ready` | Safe to include in a delivery package. |
| `delivered` | Shared with the customer. |
| `superseded` | Replaced by a newer artifact. |

Delivery should be blocked unless required artifacts are `founder-reviewed` or `customer-ready`. If an explicit override is added later, it must emit a loud warning in the CLI, audit log, and delivery package README.

## Delivery Package

`atlas package-delivery --workspace <name>` should create:

```text
.workspaces/<name>/delivery/<name>-atlas-pilot/
README.md
pilot-readout.md
engineering-opportunities.md
remediation-plans/
evidence-summary.md
next-steps.md
```

### Package requirements

| Requirement | Detail |
|---|---|
| No raw AWS by default | Include summaries and evidence references, not full provider payloads. |
| No full repo by default | Include file/path references and relevant excerpts only when approved. |
| Disclaimer | State Atlas was read-only, local/operator-run, and did not merge, deploy, mutate AWS, or bypass CI/CD. |
| What Atlas did not do | Explicitly list missing data, skipped AI, unsupported remediation paths, unapproved diffs, and customer-owned decisions. |
| Next decisions | Include stop, investigate, remediate, repeat, expand, or defer options. |
| Review status | Show artifact status and reviewer/date when available. |
| Traceability | Link opportunities to evidence summaries, graph context, plans, approvals, and audit events. |

## Report Quality Requirements

### Engineering Opportunities

Engineering Opportunities must be decision-ready, not raw findings.

| Required field | Quality bar |
|---|---|
| Problem | Specific technical or business issue Atlas believes exists. |
| Impact | Why it matters: cost, scalability, reliability, architecture quality, operational risk, or delivery drag. |
| Evidence | Source evidence summaries, graph relationships, IaC references, cost/usage signals when used, and assumptions. |
| Graph context | Affected resources, repositories, services, dependencies, owners, and confidence limits. |
| Recommendation | Clear preferred action: act, defer, investigate, or reject. |
| Alternatives | Reasonable options, including doing nothing when defensible. |
| Tradeoffs | Cost, complexity, risk, operational consequence, and delivery effort. |
| Confidence | High/medium/low with explanation tied to evidence quality and missing context. |
| Priority | Why this outranks or does not outrank other opportunities. |
| Estimated impact | Ranges or qualitative estimates only when evidence supports them; no invented savings. |
| Remediation path | Whether CDK/Terraform planning, PR/diff, or guidance-only is appropriate. |
| Why it might be wrong | Explicit uncertainty, stale data, missing relationships, or customer context needed. |
| Next action | One concrete next operator or customer action. |

### Pilot readout

The pilot readout must help a CTO, technical founder, or VP Engineering decide what to do next without reading raw findings.

| Required section | Quality bar |
|---|---|
| Executive summary | Customer/workspace, pilot dates, buyer/reviewers, strongest opportunity, confidence, recommendation, and decision needed. |
| Connected scope | Included/excluded AWS accounts, regions, repositories, signals, time window, and safety boundary. |
| Top Engineering Opportunities | Ranked list plus problem, evidence, graph context, impact hypothesis, tradeoffs, recommendation, and confidence. |
| Evidence and confidence | AWS metadata, Cost Explorer/usage, repo context, runtime/customer input when available, missing evidence, and confidence effect. |
| Recommended roadmap | Sequenced actions with owner, timing, and dependencies. |
| Remediation Plan summary | Approved opportunity, plan version, scope, non-scope, path, sensitive changes, validation, rollback expectation, and open risks. |
| PR or patch output | Artifact type, repo, branch/reference, files touched, why generated or not, customer review focus, and CI/CD expectation. |
| Estimated impact | Cost, scalability, architecture quality, operational risk, and engineering time using ranges or qualitative language when needed. |
| Risks and assumptions | Risks, assumptions, impact, and mitigation. |
| Customer decisions | Accept/reject/defer/investigate, planning decision, PR generation decision, and commercial next step. |
| Next steps | Owner, due date when known, notes, and one clear Atlas recommendation. |

## Client-Pilot Safety Boundaries

These boundaries must be enforced where possible and warned everywhere else.

| Boundary | Required behavior |
|---|---|
| No AWS mutation | Collectors must remain read-only and must not call mutating AWS APIs. |
| No deploy | Atlas must not deploy infrastructure. |
| No merge | Atlas must not merge PRs or auto-approve generated changes. |
| No CI/CD bypass | Atlas may observe checks but must not skip or replace customer CI/CD. |
| No raw evidence by default | Delivery packages include summaries/references unless raw export is explicitly approved. |
| No AI submission without previewable context | Operator can inspect bounded context before provider calls. |
| No PR/diff without approval | Readiness validation blocks missing planning or PR/diff approval. |
| No customer delivery without review | Delivery blocks unless artifacts are reviewed or an explicit override warning exists. |
| Sensitive changes require warning | IAM, networking, deletion, retention, encryption, public exposure, and production scope are flagged. |

## Workspace Deletion

`atlas delete-workspace <name>` deletes customer-sensitive local state and must require strong confirmation.

Minimum confirmation behavior:

```text
This will permanently delete .workspaces/<name>/.
Type DELETE <name> to continue:
```

Deletion must record an audit event before removing files when possible. If the audit log is deleted with the workspace, the CLI should still show a final confirmation summary.

## Tests Required

| Test area | Required coverage |
|---|---|
| Sample demo workflow | `load-sample` plus `demo` produces opportunities, readout, remediation plan, and delivery-ready paths. |
| Readiness validation | Ready yes/no, blockers, warnings, next action, and every major missing-data/safety case. |
| No-AI analysis | `analyze --no-ai` produces outputs, assumptions, and no provider call. |
| AI preview | Full workspace and `--opportunity-id` preview are bounded and do not submit. |
| Audit log | Commands, params, files changed, failures, AI, report, remediation, review, and delivery events are recorded. |
| Review changes | `list-artifacts` and `mark-reviewed` show and update statuses correctly. |
| Delivery package | Required files exist, raw AWS/full repo are excluded by default, disclaimers are present, status is shown. |
| Deletion confirmation | Wrong confirmation does not delete; exact `DELETE <name>` does. |
| Report sections | Engineering Opportunities and pilot readout contain all required sections and explicit missing-evidence warnings. |

## Implementation Order

1. Add audit event primitives and artifact metadata because later commands need traceability.
2. Add sample loader and `atlas demo` to preserve demo speed.
3. Add no-AI analysis contract and AI context preview before provider-backed AI work expands.
4. Add artifact listing, review status transitions, and readiness validation.
5. Add delivery package generation and workspace deletion confirmation.
6. Tighten report templates and tests for required sections.

## Pilot Exit Criteria

Atlas Local is pilot-ready when:

- [ ] A demo can be run from two commands and produces opportunities, readout, and one remediation plan.
- [ ] A real workspace can run without AI and still produce useful, assumption-marked outputs.
- [ ] AI cannot be submitted without previewable bounded context.
- [ ] Readiness validation blocks unsafe delivery, remediation planning, and PR/diff generation.
- [ ] Reports and plans carry review status.
- [ ] The delivery package excludes raw AWS and full repo content by default.
- [ ] The audit log reconstructs commands, artifacts, approvals, warnings, and failures.
- [ ] Tests cover the pilot safety gates and required report sections.
