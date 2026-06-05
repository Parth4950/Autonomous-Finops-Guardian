# Project Architecture

This document describes the planned end-to-end architecture for **Autonomous FinOps Guardian** — an AI-powered cloud cost optimization platform that discovers idle AWS resources, predicts utilization, assesses risk, quantifies waste, and produces human-approved remediation plans.

## Design Principles

- **Separation of concerns** — Discovery, ML inference, risk analysis, financial auditing, planning, and execution live in distinct modules.
- **Human-in-the-loop** — No remediation is applied without explicit human approval.
- **Observable pipeline** — Each stage emits structured outputs that downstream agents consume.
- **Fail-safe defaults** — Risk and audit gates block high-impact actions before they reach the executor.

## Pipeline Overview

```
Scout Agent
    ↓
Isolation Forest
    ↓
Prophet Forecasting
    ↓
Risk Assessor
    ↓
Auditor
    ↓
Planner
    ↓
Human Approval
    ↓
Executor
```

## Stage-by-Stage Responsibilities

### 1. Scout Agent

**Location:** `agents/scout/`

Discovers AWS resources and ingests utilization metrics (CloudWatch, Cost Explorer, resource inventory). Produces normalized resource snapshots and time-series metric bundles for downstream analysis.

**Outputs:** Resource catalog, utilization time series, metadata tags (owner, environment, service).

---

### 2. Isolation Forest

**Location:** `ml/isolation_forest/`

Applies unsupervised anomaly detection on utilization features to flag statistically idle or abnormal resources. Separates noise from genuine underutilization candidates.

**Inputs:** Scout metric features (CPU, network, I/O, request counts).

**Outputs:** Anomaly scores, idle-resource candidates with confidence bands.

---

### 3. Prophet Forecasting

**Location:** `ml/forecasting/`

Forecasts future utilization trajectories for flagged resources using Facebook Prophet (or equivalent time-series models). Distinguishes temporary dips from sustained idle patterns.

**Inputs:** Historical utilization from Scout; candidates from Isolation Forest.

**Outputs:** Forecasted utilization curves, trend components, projected idle windows.

---

### 4. Risk Assessor Agent

**Location:** `agents/risk_assessor/`

Evaluates operational risk of acting on each candidate — blast radius, dependency graphs, SLA impact, production vs. non-production context, and rollback complexity.

**Inputs:** Resource metadata, forecast results, dependency context.

**Outputs:** Risk scores, risk categories (low / medium / high / critical), blocking flags.

---

### 5. Auditor Agent

**Location:** `agents/auditor/`

Quantifies financial waste — monthly run-rate, projected savings, amortized costs, and budget impact. Aligns technical findings with FinOps KPIs.

**Inputs:** Resource pricing data, utilization forecasts, risk classifications.

**Outputs:** Waste estimates, savings projections, cost attribution by team/service.

---

### 6. Planner Agent

**Location:** `agents/planner/`

Synthesizes scout, ML, risk, and audit outputs into structured, human-readable remediation plans. Each plan includes rationale, estimated savings, risk summary, and recommended actions (rightsizing, scheduling, termination).

**Inputs:** All upstream agent and ML outputs.

**Outputs:** Remediation plan documents ready for human review.

---

### 7. Human Approval

**Location:** Future API / frontend workflow (not yet implemented).

Presents plans to operators for review. Supports approve, reject, defer, and partial-approval flows. Approved plans are persisted and handed to the executor.

**Outputs:** Approved action manifests with audit trail.

---

### 8. Executor Agent

**Location:** `agents/executor/`

Applies only human-approved remediation actions against AWS. Supports dry-run mode, idempotent execution, and post-action verification.

**Inputs:** Approved remediation manifests.

**Outputs:** Execution logs, rollback handles, verification results.

---

## Supporting Layers

| Layer | Path | Role |
|-------|------|------|
| Backend services | `backend/services/` | Orchestration, API handlers (future), workflow coordination |
| Configuration | `backend/config/` | Environment validation, feature flags, regional defaults |
| Database | `database/` | Persistence for resources, plans, approvals, audit logs |
| Synthetic data | `synthetic_data/` | Development datasets mirroring production metric shapes |
| Tests | `tests/` | Unit and integration coverage across agents and ML modules |

## Data Flow Summary

1. **Scout** collects raw AWS signals.
2. **Isolation Forest** narrows the candidate set via anomaly detection.
3. **Prophet** forecasts whether idle patterns will persist.
4. **Risk Assessor** gates unsafe actions.
5. **Auditor** attaches dollar values to each opportunity.
6. **Planner** assembles actionable, explainable plans.
7. **Human Approval** authorizes changes.
8. **Executor** implements approved remediations safely.

## Future Extensions

- LangGraph-based agent orchestration with stateful workflows
- FastAPI REST layer and React dashboard
- Real-time alerting via SNS / Slack integrations
- Multi-account and multi-region AWS organization support
