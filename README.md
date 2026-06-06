# Autonomous FinOps Guardian

An AI-powered cloud cost optimization platform that discovers idle AWS resources, predicts future utilization using machine learning, assesses operational risk, calculates financial waste, and generates human-approved remediation plans.

[![Repository](https://img.shields.io/badge/GitHub-Autonomous--Finops--Guardian-blue)](https://github.com/Parth4950/Autonomous-Finops-Guardian)

---

## Project Overview

Cloud spend often includes significant waste from underutilized or idle resources. Manual FinOps reviews are slow, inconsistent, and difficult to scale across large AWS estates.

**Autonomous FinOps Guardian** automates the discovery-to-remediation lifecycle:

1. **Discover** — Scan AWS for EC2 instances, EBS volumes, and CloudWatch utilization metrics.
2. **Detect** — Flag anomalous idle resources with Isolation Forest.
3. **Predict** — Forecast whether idle patterns are temporary or sustained with Prophet.
4. **Assess** — Score operational risk with deterministic rules and Gemini explanations.
5. **Quantify** — Calculate financial waste, savings, and executive-level cost reports.
6. **Plan** — Generate clear, human-reviewable remediation plans. *(planned)*
7. **Execute** — Apply only approved actions with full auditability. *(planned)*

The platform is designed for production use: modular agents, validated configuration, deterministic decision engines, AI-assisted reporting, and a human-in-the-loop approval gate before any remediation runs.

---

## Current Progress

| Phase | Status | Description |
|-------|--------|-------------|
| Project scaffolding | ✅ Done | Folder structure, config, docs, `.gitignore` |
| AWS connectivity | ✅ Done | Boto3 credential verification via `test_aws.py` |
| Scout Agent | ✅ Done | EC2, EBS discovery + CloudWatch metrics |
| Synthetic dataset | ✅ Done | 550 labeled resources for ML development |
| Isolation Forest | ✅ Done | Unsupervised anomaly detection |
| Prophet forecasting | ✅ Done | 30-day CPU utilization forecasts |
| Risk Assessor | ✅ Done | Deterministic rules + Gemini explanations |
| Auditor Agent | ✅ Done | Savings analysis + executive reports |
| Planner / Executor | 🔜 Planned | Remediation plans and approved execution |
| FastAPI + React UI | 🔜 Planned | API layer and operator dashboard |
| LangGraph orchestration | 🔜 Planned | Stateful agent workflow |

---

## Architecture Overview

```
Scout Agent → Isolation Forest → Prophet Forecasting → Risk Assessor
    → Auditor → Planner → Human Approval → Executor
         ✅            ✅              ✅            ✅         ✅
```

| Component | Responsibility | Status |
|-----------|----------------|--------|
| **Scout Agent** | AWS resource discovery and CloudWatch metric ingestion | ✅ Implemented |
| **Isolation Forest** | Unsupervised anomaly detection for idle candidates | ✅ Implemented |
| **Prophet Forecasting** | Time-series utilization prediction and waste probability | ✅ Implemented |
| **Risk Assessor** | Deterministic risk scoring + Gemini explanations | ✅ Implemented |
| **Auditor** | Financial waste quantification and executive reporting | ✅ Implemented |
| **Planner** | Remediation plan generation | Planned |
| **Human Approval** | Operator review and authorization | Planned |
| **Executor** | Safe, auditable application of approved changes | Planned |

See [docs/project_architecture.md](docs/project_architecture.md) for detailed stage descriptions and data flows.

### Scout Agent

```
ScoutAgent
    ├── EC2Scanner        → DescribeInstances (ID, type, state, tags)
    ├── EBSScanner        → DescribeVolumes (size, state, unattached flag)
    └── MetricsCollector  → CloudWatch GetMetricStatistics (CPU, network)
```

### Risk Assessor (rules + AI explanations)

```
Waste Score → Infrastructure Metadata → Risk Rules Engine → Risk Score
    → Gemini Explanation Layer → Human-Readable Assessment
```

Gemini **explains** risk — it never determines risk scores. All scoring is deterministic and auditable.

### Auditor (financial analysis)

```
Risk Assessment → Cost Analysis → Savings Estimation → Gemini Executive Report
```

---

## Agents

| Agent | Package | Status |
|-------|---------|--------|
| Scout | `agents/scout/` | ✅ EC2, EBS, CloudWatch metrics |
| Risk Assessor | `agents/risk_assessor/` | ✅ Rules engine + Gemini explainer |
| Auditor | `agents/auditor/` | ✅ Cost analysis + executive reporter |
| Predictor | `agents/predictor/` | Planned (orchestration layer) |
| Planner | `agents/planner/` | Planned |
| Executor | `agents/executor/` | Planned |

---

## ML Models

| Model | Package | Status | Purpose |
|-------|---------|--------|---------|
| Isolation Forest | `ml/isolation_forest/` | ✅ Implemented | Detect anomalous / idle utilization patterns |
| Prophet Forecasting | `ml/forecasting/` | ✅ Implemented | Predict future resource utilization trends |
| Synthetic data | `synthetic_data/` | ✅ Implemented | Labeled training data (500 normal + 50 zombie) |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Cloud SDK | boto3 (AWS EC2, CloudWatch) |
| Data processing | pandas, numpy, matplotlib |
| Machine learning | scikit-learn (Isolation Forest), Prophet |
| AI explanations | google-genai (Gemini 2.0 Flash) |
| Configuration | python-dotenv |
| SSL (Windows) | pip-system-certs, certifi |
| Database | PostgreSQL via SQLAlchemy + psycopg2-binary (planned) |
| Orchestration (planned) | LangGraph |
| API (planned) | FastAPI |
| Frontend (planned) | React |

---

## Project Structure

```
autonomous-finops-guardian/
├── backend/
│   ├── config/settings.py
│   └── utils/aws_client.py
├── agents/
│   ├── scout/
│   │   ├── ec2_scanner.py
│   │   ├── ebs_scanner.py
│   │   ├── metrics_collector.py
│   │   └── scout_agent.py
│   ├── risk_assessor/
│   │   ├── risk_assessor.py
│   │   ├── gemini_explainer.py
│   │   ├── prompts/
│   │   ├── results/
│   │   └── figures/
│   ├── auditor/
│   │   ├── auditor.py
│   │   ├── gemini_reporter.py
│   │   ├── prompts/
│   │   ├── results/
│   │   └── figures/
│   ├── planner/                   # (planned)
│   └── executor/                  # (planned)
├── ml/
│   ├── isolation_forest/
│   │   ├── isolation_detector.py
│   │   ├── results/
│   │   └── figures/
│   └── forecasting/
│       ├── prophet_forecaster.py
│       ├── data/
│       ├── results/
│       └── figures/
├── synthetic_data/
│   ├── generate_resources.py
│   └── cloud_resources.csv
├── docs/project_architecture.md
├── test_aws.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11 or later
- AWS account with IAM programmatic access keys
- Google AI Studio API key (optional — for Gemini explanations and reports)

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
GEMINI_API_KEY=your_gemini_api_key
```

Set `AWS_REGION` to the region where your resources live (e.g. `ap-southeast-2` for Sydney). `GEMINI_API_KEY` is optional — agents fall back to deterministic templates when unavailable.

---

## Usage

Run the pipeline in order for the full FinOps workflow:

### 1. Verify AWS connectivity

```bash
python test_aws.py
```

### 2. Scout Agent — discover AWS resources

```bash
python agents/scout/scout_agent.py
python agents/scout/metrics_collector.py
```

### 3. Generate synthetic training data

```bash
python synthetic_data/generate_resources.py
```

### 4. Isolation Forest — anomaly detection

```bash
python ml/isolation_forest/isolation_detector.py
```

### 5. Prophet — utilization forecasting

```bash
python ml/forecasting/prophet_forecaster.py
```

### 6. Risk Assessor — operational risk scoring

```bash
python agents/risk_assessor/risk_assessor.py
```

### 7. Auditor — financial waste analysis

```bash
python agents/auditor/auditor.py
```

---

## Pipeline Outputs

| Stage | Output | Key metrics |
|-------|--------|-------------|
| Scout | EC2/EBS findings | Instance metadata, unattached volumes |
| CloudWatch | Per-instance metrics | 7-day CPU and network averages |
| Isolation Forest | `predictions.csv` | Anomaly scores, precision/recall |
| Prophet | `forecast_results.csv` | 30-day forecast, waste probability |
| Risk Assessor | `risk_assessment.csv` | Risk score, level, recommendation |
| Auditor | `audit_results.csv` | Monthly/annual savings, priority score |
| Auditor | `executive_report.json` | Executive summary, key findings |

### Verified audit results (latest run)

```
Total Monthly Cost       : $21,290.72
Potential Annual Savings : $142,456.32
Safe To Remediate        : 44 resources
Manual Review Required   : 36 resources
Do Not Remediate         : 20 resources
```

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Deterministic decisions** | Risk scores and savings come from rules engines, not LLMs |
| **AI for narrative only** | Gemini explains and reports — never overrides scores |
| **Separation of concerns** | Each agent is an isolated, testable Python package |
| **Human-in-the-loop** | No remediation without explicit approval *(planned)* |
| **Graceful degradation** | Gemini fallback templates when API is unavailable |

---

## IAM Permissions

Minimum IAM policy for Scout functionality:

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

Managed policies: `AmazonEC2ReadOnlyAccess`, `CloudWatchReadOnlyAccess`

---

## Windows SSL Note

If Boto3 or Gemini fails with `SSL: CERTIFICATE_VERIFY_FAILED` on Windows:

```bash
pip install pip-system-certs certifi
```

Both are included in `requirements.txt` and configured automatically.

---

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| Day 1 | Project scaffolding, configuration, documentation | ✅ |
| Phase 2 | Scout agent — EC2/EBS discovery + CloudWatch metrics | ✅ |
| Phase 3 | ML pipeline — Isolation Forest + Prophet + synthetic data | ✅ |
| Phase 4 | Risk Assessor and Auditor agents | ✅ |
| Phase 5 | Planner agent and human approval workflow | 🔜 |
| Phase 6 | Executor agent with dry-run and rollback support | 🔜 |
| Phase 7 | FastAPI backend and React dashboard | 🔜 |
| Phase 8 | LangGraph orchestration, CI/CD, and production hardening | 🔜 |

---

## License

TBD — portfolio / demonstration project.
