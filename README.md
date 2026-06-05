# Autonomous FinOps Guardian

An AI-powered cloud cost optimization platform that discovers idle AWS resources, predicts future utilization using machine learning, assesses operational risk, calculates financial waste, and generates human-approved remediation plans.

---

## Project Overview

Cloud spend often includes significant waste from underutilized or idle resources. Manual FinOps reviews are slow, inconsistent, and difficult to scale across large AWS estates.

**Autonomous FinOps Guardian** automates the discovery-to-remediation lifecycle:

1. **Discover** — Scan AWS for resources with low or anomalous utilization.
2. **Predict** — Forecast whether idle patterns are temporary or sustained.
3. **Assess** — Score operational risk before any change is proposed.
4. **Quantify** — Calculate financial waste and projected savings.
5. **Plan** — Generate clear, human-reviewable remediation plans.
6. **Execute** — Apply only approved actions with full auditability.

The platform is designed for production use: modular agents, validated configuration, persistent audit trails, and a human-in-the-loop approval gate before any remediation runs.

---

## Architecture Overview

The system follows a linear pipeline where each stage enriches a shared context before handing off to the next:

```
Scout Agent → Isolation Forest → Prophet Forecasting → Risk Assessor
    → Auditor → Planner → Human Approval → Executor
```

| Component | Responsibility |
|-----------|----------------|
| **Scout Agent** | AWS resource discovery and metric ingestion |
| **Isolation Forest** | Unsupervised anomaly detection for idle candidates |
| **Prophet Forecasting** | Time-series utilization prediction |
| **Risk Assessor** | Operational risk scoring and gating |
| **Auditor** | Financial waste and savings quantification |
| **Planner** | Remediation plan generation |
| **Human Approval** | Operator review and authorization |
| **Executor** | Safe, auditable application of approved changes |

See [docs/project_architecture.md](docs/project_architecture.md) for detailed stage descriptions and data flows.

---

## Planned Agents

| Agent | Package | Status |
|-------|---------|--------|
| Scout | `agents/scout/` | Planned |
| Predictor | `agents/predictor/` | Planned |
| Risk Assessor | `agents/risk_assessor/` | Planned |
| Auditor | `agents/auditor/` | Planned |
| Planner | `agents/planner/` | Planned |
| Executor | `agents/executor/` | Planned |

Each agent is an isolated module with a single responsibility, enabling independent development, testing, and deployment.

---

## Planned ML Models

| Model | Package | Purpose |
|-------|---------|---------|
| Isolation Forest | `ml/isolation_forest/` | Detect anomalous / idle utilization patterns |
| Prophet Forecasting | `ml/forecasting/` | Predict future resource utilization trends |

Models consume normalized metric features from the Scout agent and feed scores and forecasts into the Risk Assessor and Auditor agents.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Cloud SDK | boto3 (AWS) |
| Data processing | pandas, numpy |
| Database | PostgreSQL via SQLAlchemy + psycopg2-binary |
| Configuration | python-dotenv |
| ML (planned) | scikit-learn (Isolation Forest), Prophet |
| Orchestration (planned) | LangGraph |
| API (planned) | FastAPI |
| Frontend (planned) | React |

---

## Project Structure

```
autonomous-finops-guardian/
├── backend/
│   ├── config/          # Environment and application settings
│   ├── services/        # Business logic and orchestration
│   └── utils/           # Shared helpers
├── agents/
│   ├── scout/           # Resource discovery
│   ├── predictor/       # Utilization forecasting orchestration
│   ├── risk_assessor/   # Operational risk evaluation
│   ├── auditor/         # Financial waste quantification
│   ├── planner/         # Remediation plan generation
│   └── executor/        # Approved action execution
├── ml/
│   ├── isolation_forest/
│   └── forecasting/
├── database/
│   ├── models/
│   └── migrations/
├── synthetic_data/      # Development datasets
├── docs/                # Architecture and design documents
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

---

## Getting Started (Day 1)

### Prerequisites

- Python 3.11 or later
- PostgreSQL (for future database integration)
- AWS credentials with read access (for future Scout agent)

### Setup

```bash
# Clone and enter the project
cd autonomous-finops-guardian

# Create a virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS / Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your AWS credentials and DATABASE_URL
```

### Verify Configuration

```python
from backend.config import get_settings

settings = get_settings()
print(settings.aws_region)
```

---

## Future Roadmap

| Phase | Focus |
|-------|-------|
| **Day 1** ✅ | Project scaffolding, configuration, documentation |
| **Phase 2** | Scout agent — AWS resource discovery and metric collection |
| **Phase 3** | ML pipeline — Isolation Forest + Prophet integration |
| **Phase 4** | Risk Assessor and Auditor agents |
| **Phase 5** | Planner agent and human approval workflow |
| **Phase 6** | Executor agent with dry-run and rollback support |
| **Phase 7** | FastAPI backend and React dashboard |
| **Phase 8** | LangGraph orchestration, CI/CD, and production hardening |

---

## License

TBD — portfolio / demonstration project.
