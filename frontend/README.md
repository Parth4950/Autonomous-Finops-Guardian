# Autonomous FinOps Guardian — Frontend

React + TypeScript operator dashboard for the Autonomous FinOps Guardian platform.

## Tech Stack

- React 18 + TypeScript
- Vite
- TailwindCSS (dark mode default)
- shadcn/ui-style components
- Tremor + Recharts
- Axios + TanStack React Query
- Lucide React + React Router

## Getting Started

**Both backend and frontend must be running.**

```bash
# Terminal 1 — from repo root
python backend/run_dev.py

# Terminal 2
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

## API Connection

| Mode | Configuration |
|------|----------------|
| **Default (dev)** | Vite proxies `/api/*` → `http://127.0.0.1:8000` |
| **Direct** | Create `frontend/.env` with `VITE_API_BASE_URL=http://127.0.0.1:8000` |

API modules live in `src/api/` (`client.ts`, `resources.ts`, `waste.ts`, etc.). React Query hooks: `useResources()`, `useWaste()`, `useRisk()`, `useAudit()`, `usePlans()`, `useApprovals()`, `useExecutions()`, `useAnomalies()`, `useForecast()`.

## Pages

| Route | Page |
|-------|------|
| `/` | Overview — KPIs, charts, **Run Cloud Scan** |
| `/resources` | Resources |
| `/anomalies` | Anomaly Detection |
| `/forecasting` | Forecasting |
| `/risk` | Risk Assessment |
| `/audit` | Audit Reports |
| `/plans` | Remediation Plans |
| `/approvals` | Approval Center |
| `/executions` | Execution History |

## Live Cloud Scan

The Overview **Run Cloud Scan** button calls `POST /scan/start` and polls `GET /scan/status`. On completion, React Query invalidates resources, waste, risk, audit, and plans queries.

## Design

Datadog-inspired dark theme with purple accent (`#7745FF`), panel-based layout, skeleton loading states, and responsive sidebar navigation.

## Build

```bash
npm run build
npm run preview
```
