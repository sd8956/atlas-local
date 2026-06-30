# First Customer Pilot Runbook

This runbook describes how to execute a first real Atlas Local pilot safely. Atlas Local is an operator-run local tool: it collects read-only evidence, analyzes it locally, gates delivery with human review and approvals, and never mutates cloud resources.

## Quick path

1. Confirm written scope with the customer.
2. Configure the workspace with allowed accounts, regions, repositories, AI policy, and Cost Explorer policy.
3. Collect read-only AWS evidence and ingest only the approved repository path.
4. Run deterministic analysis first with `--no-ai`.
5. Review artifacts manually, record approvals, validate readiness, and package delivery.
6. Delete the workspace when retention is no longer needed.

## Safety boundaries

| Boundary | Required behavior |
|---|---|
| AWS access | Use read-only credentials only. Atlas must not mutate cloud resources. |
| Repository access | Ingest only approved local paths listed in workspace scope. |
| AI | Run without AI first. Use `ai-context-preview` before provider-backed review. Respect workspace AI policy. |
| Customer delivery | Requires reviewed artifacts plus explicit `customer-delivery` approval. |
| Raw data | Do not include raw AWS evidence or full repository source in delivery packages by default. |
| Remediation | Plans are advisory. No auto-deploy, auto-merge, or CI/CD bypass. |

## Pre-pilot checklist

- [ ] Customer alias is agreed.
- [ ] Allowed AWS account IDs are confirmed.
- [ ] Allowed AWS regions are confirmed.
- [ ] Approved repository/IaC paths are confirmed.
- [ ] Cost Explorer policy is agreed: `allowed` or `not-allowed`.
- [ ] AI policy is agreed: `allowed` or `not-allowed`.
- [ ] AWS read-only profile exists locally.
- [ ] Customer understands Atlas will produce advisory artifacts, not production changes.

## Configure the workspace

```bash
.venv/bin/atlas init-workspace <customer-workspace>

.venv/bin/atlas configure-workspace \
  --workspace <customer-workspace> \
  --customer-alias "<Customer Alias>" \
  --allowed-account <aws-account-id> \
  --allowed-region <region> \
  --allowed-repo-path "<approved-repo-path>" \
  --cost-explorer allowed|not-allowed \
  --ai allowed|not-allowed

.venv/bin/atlas show-workspace --workspace <customer-workspace>
```

### Scope review

Before collecting evidence, verify that `show-workspace` matches the customer-approved scope.

| Scope item | What to verify |
|---|---|
| Customer alias | Matches the customer/pilot name used in delivery artifacts. |
| Allowed accounts | Only customer-approved AWS accounts are listed. |
| Allowed regions | Only agreed regions are listed. |
| Allowed repo paths | Only approved local repository/IaC paths are listed. |
| Cost Explorer policy | Matches customer permission and commercial expectations. |
| AI policy | Matches customer approval for provider-backed analysis. |

## Collect evidence

```bash
.venv/bin/atlas collect-aws \
  --workspace <customer-workspace> \
  --profile <readonly-profile> \
  --regions <region-list>

.venv/bin/atlas ingest-repo \
  --workspace <customer-workspace> \
  --path "<approved-repo-path>"
```

### Expected blockers

| Blocker | Meaning | Next action |
|---|---|---|
| Disallowed region | Requested collection outside workspace scope. | Reconfirm scope or rerun with allowed regions. |
| Disallowed account | STS identity is outside workspace scope. | Stop and use the correct profile/account. |
| Disallowed repo path | Repository path is outside approved scope. | Use the approved path or update scope after customer approval. |
| Missing permissions | AWS read-only role lacks a service permission. | Record as missing evidence or ask customer for read-only permission. |

## Run local analysis

Run deterministic analysis first:

```bash
.venv/bin/atlas normalize --workspace <customer-workspace>
.venv/bin/atlas build-graph --workspace <customer-workspace>
.venv/bin/atlas analyze --workspace <customer-workspace> --no-ai
```

If AI is allowed, preview context before any provider-backed review:

```bash
.venv/bin/atlas ai-context-preview --workspace <customer-workspace>
.venv/bin/atlas ai-review --workspace <customer-workspace>
```

If AI is not allowed, `ai-review` should skip with an explicit policy reason.

## Generate artifacts

```bash
.venv/bin/atlas generate-readout --workspace <customer-workspace>
.venv/bin/atlas generate-remediation-plan \
  --workspace <customer-workspace> \
  --opportunity-id <opportunity-id>
```

Review generated artifacts under `.workspaces/<customer-workspace>/reports/` and `.workspaces/<customer-workspace>/remediation/`.

## Manual review checklist

- [ ] Opportunities are evidence-bound and do not invent savings.
- [ ] Cost claims are qualitative unless Cost Explorer, usage, pricing, or customer evidence supports them.
- [ ] Sensitive findings are clearly marked.
- [ ] AI output, if any, is marked as advisory and assumption-aware.
- [ ] Remediation plans are advisory and require customer approval before action.
- [ ] Delivery package will not include raw AWS evidence or full repository source by default.

## Review, approvals, and readiness

```bash
.venv/bin/atlas list-artifacts --workspace <customer-workspace>
.venv/bin/atlas mark-reviewed --workspace <customer-workspace> --artifact <artifact-id>

.venv/bin/atlas record-approval \
  --workspace <customer-workspace> \
  --type customer-delivery \
  --approved-by "<operator-name>" \
  --note "Reviewed scope, safety boundaries, and customer-ready artifacts."

.venv/bin/atlas validate-readiness --workspace <customer-workspace>
```

Use additional approval types only when the customer/operator explicitly approves that workflow:

| Approval type | When to record |
|---|---|
| `ai-use` | Before provider-backed AI review when workspace AI policy is `allowed`. |
| `remediation-planning` | Before presenting or expanding remediation planning. |
| `pr-diff-generation` | Reserved for future PR/diff workflows; currently unsupported. |
| `customer-delivery` | Before creating a customer-facing delivery package. |

## Package delivery

```bash
.venv/bin/atlas package-delivery --workspace <customer-workspace>
```

Expected package path:

```text
.workspaces/<customer-workspace>/delivery/<customer-workspace>-atlas-pilot/
```

Before sharing, inspect:

- [ ] `README.md`
- [ ] `pilot-readout.md`
- [ ] `engineering-opportunities.md`
- [ ] `evidence-summary.md`
- [ ] `next-steps.md`
- [ ] `remediation-plans/`

Confirm no raw AWS evidence or full repository source is included unless separately approved outside the default workflow.

## Audit review

```bash
.venv/bin/atlas audit-log --workspace <customer-workspace>
```

Use the audit log to reconstruct:

- commands executed
- scope configuration
- evidence collection results
- skipped AI or Cost Explorer by policy
- artifact review status changes
- approvals
- readiness validation
- delivery package creation

## Cleanup after pilot

When retention is no longer needed:

```bash
.venv/bin/atlas delete-workspace <customer-workspace>
```

The command requires exact confirmation:

```text
DELETE <customer-workspace>
```

Do not delete before delivery, audit, and retention expectations are satisfied.

## If readiness is blocked

| Blocker | How to resolve |
|---|---|
| Missing AWS evidence | Re-run collection or record the evidence gap in delivery. |
| Missing repo evidence | Ingest the approved repository path or update scope after approval. |
| Missing human review | Run `list-artifacts`, inspect artifacts, then `mark-reviewed`. |
| Missing approval | Use `record-approval` only after real operator/customer approval. |
| AI skipped | Accept if AI is `not-allowed`; otherwise preview context and run AI only after approval. |
| Cost Explorer skipped | Accept if `not-allowed`; otherwise request permission or keep cost claims qualitative. |
| Unsupported PR/diff | Keep as advisory; do not generate production changes. |

## Done criteria

- [ ] Workspace scope matches customer agreement.
- [ ] Read-only AWS collection completed or missing permissions are documented.
- [ ] Approved repository path was ingested.
- [ ] Deterministic analysis completed.
- [ ] AI, if used, was previewed and approved.
- [ ] Artifacts were manually reviewed.
- [ ] `customer-delivery` approval was recorded.
- [ ] `validate-readiness` returns ready or documented warnings only.
- [ ] Delivery package was inspected before sharing.
- [ ] Audit log reconstructs the pilot.
