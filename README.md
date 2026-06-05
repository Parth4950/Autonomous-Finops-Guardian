# Autonomous FinOps Guardian

An AI-powered cloud cost optimization platform that discovers idle AWS resources, predicts future utilization using machine learning, assesses operational risk, calculates financial waste, and generates human-approved remediation plans.

[![Repository](https://img.shields.io/badge/GitHub-Autonomous--Finops--Guardian-blue)](https://github.com/Parth4950/Autonomous-Finops-Guardian)

---

## Project Overview

Cloud spend often includes significant waste from underutilized or idle resources. Manual FinOps reviews are slow, inconsistent, and difficult to scale across large AWS estates.

**Autonomous FinOps Guardian** automates the discovery-to-remediation lifecycle:

1. **Discover** — Scan AWS for EC2 instances, EBS volumes, and CloudWatch utilization metrics.
2. **Predict** — Forecast whether idle patterns are temporary or sustained.
3. **Assess** — Score operational risk before any change is proposed.
4. **Quantify** — Calculate financial waste and projected savings.
5. **Plan** — Generate clear, human-reviewable remediation plans.
6. **Execute** — Apply only approved actions with full auditability.

The platform is designed for production use: modular agents, validated configuration, persistent audit trails, and a human-in-the-loop approval gate before any remediation runs.

---

## Current Progress

| Phase | Status | Description |
|-------|--------|-------------|
| Project scaffolding | ✅ Done | Folder structure, config, docs, `.gitignore` |
| AWS connectivity | ✅ Done | Boto3 credential verification via `test_aws.py` |
| Scout Agent — EC2 | ✅ Done | Discover all EC2 instances with metadata and tags |
| Scout Agent — EBS | ✅ Done | Discover EBS volumes and flag unattached volumes |
| CloudWatch metrics | ✅ Done | 7-day CPU and network averages per EC2 instance |
| Isolation Forest | 🔜 Planned | Unsupervised idle-resource detection |
| Prophet forecasting | 🔜 Planned | Utilization trend prediction |
| Risk Assessor / Auditor | 🔜 Planned | Risk scoring and waste quantification |
| Planner / Executor | 🔜 Planned | Remediation plans and approved execution |
| FastAPI + React UI | 🔜 Planned | API layer and operator dashboard |

---

## Architecture Overview

The system follows a linear pipeline where each stage enriches a shared context before handing off to the next:

```
Scout Agent → Isolation Forest → Prophet Forecasting → Risk Assessor
    → Auditor → Planner → Human Approval → Executor
```

| Component | Responsibility | Status |
|-----------|----------------|--------|
| **Scout Agent** | AWS resource discovery and CloudWatch metric ingestion | ✅ Implemented |
| **Isolation Forest** | Unsupervised anomaly detection for idle candidates | Planned |
| **Prophet Forecasting** | Time-series utilization prediction | Planned |
| **Risk Assessor** | Operational risk scoring and gating | Planned |
| **Auditor** | Financial waste and savings quantification | Planned |
| **Planner** | Remediation plan generation | Planned |
| **Human Approval** | Operator review and authorization | Planned |
| **Executor** | Safe, auditable application of approved changes | Planned |

See [docs/project_architecture.md](docs/project_architecture.md) for detailed stage descriptions and data flows.

### Scout Agent (implemented)

```
ScoutAgent
    ├── EC2Scanner        → DescribeInstances (ID, type, state, tags)
    ├── EBSScanner        → DescribeVolumes (size, state, unattached flag)
    └── MetricsCollector  → CloudWatch GetMetricStatistics (CPU, network)
```

All Scout modules share a single `AWSClientHelper` that loads credentials from `.env`.

---

## Agents

| Agent | Package | Status |
|-------|---------|--------|
| Scout | `agents/scout/` | ✅ EC2, EBS, CloudWatch metrics |
| Predictor | `agents/predictor/` | Planned |
| Risk Assessor | `agents/risk_assessor/` | Planned |
| Auditor | `agents/auditor/` | Planned |
| Planner | `agents/planner/` | Planned |
| Executor | `agents/executor/` | Planned |

---

## ML Models (planned)

| Model | Package | Purpose |
|-------|---------|---------|
| Isolation Forest | `ml/isolation_forest/` | Detect anomalous / idle utilization patterns |
| Prophet Forecasting | `ml/forecasting/` | Predict future resource utilization trends |

Scout's `MetricsCollector` already exposes reusable methods (`build_feature_vector`, `get_time_series_payload`) for these models.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Cloud SDK | boto3 (AWS EC2, CloudWatch) |
| Data processing | pandas, numpy |
| Database | PostgreSQL via SQLAlchemy + psycopg2-binary (planned) |
| Configuration | python-dotenv |
| SSL (Windows) | pip-system-certs |
| ML (planned) | scikit-learn (Isolation Forest), Prophet |
| Orchestration (planned) | LangGraph |
| API (planned) | FastAPI |
| Frontend (planned) | React |

---

## Project Structure

```
autonomous-finops-guardian/
├── backend/
│   ├── config/
│   │   └── settings.py          # Environment validation
│   ├── services/                  # Business logic (future)
│   └── utils/
│       └── aws_client.py          # Shared Boto3 client factory
├── agents/
│   └── scout/
│       ├── ec2_scanner.py         # EC2 instance discovery
│       ├── ebs_scanner.py         # EBS volume discovery
│       ├── metrics_collector.py   # CloudWatch metric aggregation
│       └── scout_agent.py         # Scout orchestrator + CLI
├── ml/
│   ├── isolation_forest/          # (planned)
│   └── forecasting/               # (planned)
├── database/
│   ├── models/                    # (planned)
│   └── migrations/                # (planned)
├── docs/
│   └── project_architecture.md
├── synthetic_data/
├── tests/
├── test_aws.py                    # AWS connectivity verification
├── .env.example
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- AWS account with an IAM user and programmatic access keys
- IAM permissions for EC2 read, CloudWatch metrics read (see below)

### Setup

```bash
git clone https://github.com/Parth4950/Autonomous-Finops-Guardian.git
cd Autonomous-Finops-Guardian

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

### Configure `.env`

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-southeast-2
DATABASE_URL=postgresql://user:pass@localhost:5432/finops
```

Set `AWS_REGION` to the region where your resources live (e.g. `ap-southeast-2` for Sydney).

---

## Usage

### 1. Verify AWS connectivity

```bash
python test_aws.py
```

Expected output:

```
[SUCCESS] AWS authentication successful!

Available AWS regions:
----------------------------------------
  - ap-southeast-2
  ...
```

### 2. Run Scout Agent (EC2 + EBS discovery)

```bash
python agents/scout/scout_agent.py
```

Discovers all EC2 instances and EBS volumes in your configured region. Flags unattached EBS volumes (`state: available`) as FinOps waste candidates.

### 3. Collect CloudWatch metrics

```bash
python agents/scout/metrics_collector.py
```

Retrieves 7-day averages for each discovered EC2 instance:

| Metric | Description |
|--------|-------------|
| `CPUUtilization` | Average CPU usage (%) |
| `NetworkIn` | Average inbound bytes per hour |
| `NetworkOut` | Average outbound bytes per hour |

Example output:

```
=== CLOUDWATCH METRICS ===

--- Instance 1 ---
Instance ID: i-0a1913f217d016234
Avg CPU (%): 0.93
Avg Network In (bytes): 401.4
Avg Network Out (bytes): 427.8
Lookback (days): 7
```

---

## IAM Permissions

Minimum IAM policy for current Scout functionality:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeRegions",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

Or attach these managed policies for development:

- `AmazonEC2ReadOnlyAccess`
- `CloudWatchReadOnlyAccess`

---

## Windows SSL Note

If Boto3 fails with `SSL: CERTIFICATE_VERIFY_FAILED` on Windows, install the bundled certificate helper:

```bash
pip install pip-system-certs
```

This is already included in `requirements.txt` and imported automatically by `test_aws.py` and `backend/utils/aws_client.py`.

---

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| Day 1 | Project scaffolding, configuration, documentation | ✅ |
| Phase 2 | Scout agent — EC2/EBS discovery + CloudWatch metrics | ✅ |
| Phase 3 | ML pipeline — Isolation Forest + Prophet integration | 🔜 |
| Phase 4 | Risk Assessor and Auditor agents | 🔜 |
| Phase 5 | Planner agent and human approval workflow | 🔜 |
| Phase 6 | Executor agent with dry-run and rollback support | 🔜 |
| Phase 7 | FastAPI backend and React dashboard | 🔜 |
| Phase 8 | LangGraph orchestration, CI/CD, and production hardening | 🔜 |

---

## License

TBD — portfolio / demonstration project.
