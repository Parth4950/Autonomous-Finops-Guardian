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
6. **Plan** — Generate deterministic remediation plans with Gemini justifications.
7. **Approve** — Human-in-the-loop governance before any action runs.
8. **Execute** — Apply approved actions in simulation mode (real AWS hooks reserved).

The platform uses modular agents, a FastAPI backend, and a React operator dashboard. Deterministic engines make decisions; Gemini explains and reports — never overrides scores.

---

## Current Progress

| Phase | Status | Description |
|-------|--------|-------------|
| Scout Agent | ✅ Done | EC2, EBS discovery + CloudWatch metrics |
| Synthetic dataset | ✅ Done | 550 labeled resources for ML development |
| Isolation Forest | ✅ Done | Unsupervised anomaly detection |
| Prophet forecasting | ✅ Done | 30-day CPU utilization forecasts |
| Risk Assessor | ✅ Done | Deterministic rules + Gemini explanations |
| Auditor Agent | ✅ Done | Savings analysis + executive reports |
| Planner Agent | ✅ Done | Deterministic actions + Gemini justifications |
| Approval Workflow | ✅ Done | Human governance queue |
| Executor Agent | ✅ Done | Simulation mode + rollback planning |
| FastAPI backend | ✅ Done | REST API over agent pipeline outputs |
| React dashboard | ✅ Done | Full operator UI with live API data |
| Live Cloud Scan | ✅ Done | Re-run pipeline from Overview (UI button) |
| LangGraph orchestration | 🔜 Planned | Stateful agent workflow |

---

## Architecture

```
Scout Agent → Isolation Forest → Prophet → Risk Assessor → Auditor
    → Planner → Human Approval → Executor
         ✅            ✅           ✅          ✅         ✅      ✅         ✅
                              ↓
                    FastAPI REST API  ←→  React Dashboard
```

| Component | Responsibility | Status |
|-----------|----------------|--------|
| **Scout Agent** | AWS resource discovery and CloudWatch metrics | ✅ Implemented |
| **Isolation Forest** | Unsupervised anomaly detection | ✅ Implemented |
| **Prophet Forecasting** | Utilization prediction and waste probability | ✅ Implemented |
| **Risk Assessor** | Deterministic risk scoring + Gemini explanations | ✅ Implemented |
| **Auditor** | Financial waste quantification and executive reporting | ✅ Implemented |
| **Planner** | Remediation plan generation | ✅ Implemented |
| **Human Approval** | Operator review and authorization | ✅ Implemented |
| **Executor** | Simulated remediation with rollback plans | ✅ Implemented |
| **FastAPI** | REST API for dashboard and integrations | ✅ Implemented |
| **React UI** | Executive FinOps dashboard | ✅ Implemented |

See [docs/project_architecture.md](docs/project_architecture.md) for detailed stage descriptions.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Cloud SDK | boto3 (AWS EC2, CloudWatch) |
| Data processing | pandas, numpy, matplotlib |
| Machine learning | scikit-learn (Isolation Forest), Prophet |
| AI explanations | google-genai (Gemini 2.5 Flash) |
| API | FastAPI, Uvicorn |
| Frontend | React 18, TypeScript, Vite, TailwindCSS |
| UI components | shadcn/ui-style, Tremor, Recharts |
| Data fetching | Axios, TanStack React Query |
| Configuration | python-dotenv |

---

## Project Structure

```
autonomous-finops-guardian/
├── backend/                 # FastAPI REST API
│   ├── api/                 # Route handlers
│   ├── schemas/             # Pydantic models
│   ├── services/            # Business logic + scan orchestration
│   ├── run_dev.py           # Dev server (safe reload for cloud scans)
│   └── main.py
├── frontend/                # React dashboard (see frontend/README.md)
├── agents/
│   ├── scout/               # AWS discovery
│   ├── risk_assessor/
│   ├── auditor/
│   ├── planner/
│   └── executor/
├── ml/
│   ├── isolation_forest/
│   └── forecasting/
├── workflow/                # Human approval queue
├── synthetic_data/
├── docs/
├── test_aws.py
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for dashboard)
- AWS account with IAM keys (optional — for Scout / real execution)
- Google AI Studio API key (optional — Gemini fallbacks when unavailable)

### 1. Clone and install (Python)

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

### 2. Configure `.env`

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-southeast-2
GEMINI_API_KEY=your_gemini_api_key
EXECUTION_MODE=simulation
```

`GEMINI_API_KEY` and AWS credentials are optional for the default dashboard workflow, which reads **synthetic pipeline outputs**. Agents fall back to deterministic templates when Gemini is unavailable.

### 3. Install frontend

```bash
cd frontend
npm install
cd ..
```

### 4. Run the pipeline (first time)

```bash
python synthetic_data/generate_resources.py
python ml/isolation_forest/isolation_detector.py
python ml/forecasting/prophet_forecaster.py
python ml/forecasting/export_forecast_json.py
python agents/risk_assessor/risk_assessor.py
python agents/auditor/auditor.py
python agents/planner/planner.py
python workflow/approval_manager.py
```

Or click **Run Cloud Scan** on the Overview page after starting the API and UI (see below).

### 5. Start the dashboard

**Terminal 1 — API** (use `run_dev.py` so file writes during scans do not restart the server):

```bash
python backend/run_dev.py
```

**Terminal 2 — UI:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. API docs: **http://127.0.0.1:8000/docs**

> Both servers must be running. The UI proxies `/api/*` → `http://127.0.0.1:8000`. Optional: set `VITE_API_BASE_URL=http://127.0.0.1:8000` in `frontend/.env` to call the API directly.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/resources` | Cloud resource inventory |
| GET | `/waste` | Waste scores (ML + risk merge) |
| GET | `/risk` | Risk assessments |
| GET | `/audit` | Audit results |
| GET | `/audit/report` | Gemini executive report |
| GET | `/anomalies` | Isolation Forest dashboard data |
| GET | `/forecast` | Prophet forecast dashboard data |
| GET | `/plans` | Remediation plans |
| GET | `/approvals` | Approval queue |
| POST | `/approve/{id}` | Approve a plan |
| POST | `/reject/{id}` | Reject a plan |
| GET | `/executions` | Execution history |
| POST | `/execute/{id}` | Trigger remediation (simulation) |
| POST | `/scan/start` | Run full FinOps pipeline (background) |
| GET | `/scan/status` | Cloud scan progress |

---

## Dashboard Pages

| Route | Page |
|-------|------|
| `/` | Overview — KPIs, charts, **Run Cloud Scan** |
| `/resources` | Resource inventory |
| `/anomalies` | Isolation Forest results |
| `/forecasting` | Prophet CPU forecasts |
| `/risk` | Risk assessment |
| `/audit` | Audit reports + executive summary |
| `/plans` | Remediation plans |
| `/approvals` | Approval center |
| `/executions` | Execution history |

---

## Live Cloud Scan

The **Run Cloud Scan** button on the Overview page triggers `POST /scan/start`, which re-runs the local FinOps pipeline in the background:

1. Regenerate synthetic resources
2. Isolation Forest detection
3. Prophet forecasting + export
4. Risk assessment
5. Financial audit
6. Remediation planning

This refreshes dashboard data from updated CSV/JSON outputs. It does **not** call the Scout Agent or live AWS today — Scout remains available via CLI for real discovery.

---

## CLI Pipeline (manual)

```bash
python test_aws.py                              # Verify AWS connectivity
python agents/scout/scout_agent.py              # Live AWS discovery (optional)
python synthetic_data/generate_resources.py
python ml/isolation_forest/isolation_detector.py
python ml/forecasting/prophet_forecaster.py
python agents/risk_assessor/risk_assessor.py
python agents/auditor/auditor.py
python agents/planner/planner.py
python workflow/approval_manager.py
python agents/executor/executor.py
```

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Deterministic decisions** | Risk scores, actions, and savings from rules engines |
| **AI for narrative only** | Gemini explains and reports — never overrides scores |
| **Separation of concerns** | Isolated, testable agent packages |
| **Human-in-the-loop** | No execution without approval |
| **Graceful degradation** | Template fallbacks when Gemini is unavailable |
| **Safe execution default** | `EXECUTION_MODE=simulation` unless explicitly enabled |

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

---

## Windows Notes

If Boto3 or Gemini fails with `SSL: CERTIFICATE_VERIFY_FAILED`:

```bash
pip install pip-system-certs certifi
```

Both are in `requirements.txt` and configured automatically.

When running the API during cloud scans, always use:

```bash
python backend/run_dev.py
```

Plain `uvicorn --reload` on the whole repo will restart the API when pipeline CSV/JSON files change, causing **Network Error** in the UI.

---

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| ML + agents pipeline | Isolation Forest, Prophet, Risk, Audit, Plan, Execute | ✅ |
| FastAPI + React dashboard | Live API-backed operator UI | ✅ |
| Live AWS scan integration | Wire Scout output into dashboard pipeline | 🔜 |
| LangGraph orchestration | Stateful multi-agent workflow | 🔜 |
| PostgreSQL persistence | Replace CSV/JSON file stores | 🔜 |

---

## License

TBD — portfolio / demonstration project.
