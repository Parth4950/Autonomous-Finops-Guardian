# Deploy: Vercel (frontend) + Render (backend)

Host the **React dashboard** on Vercel and the **FastAPI API** on Render. The hosted demo serves **bundled synthetic pipeline data** — do not put personal AWS credentials on Render.

## Architecture

```
Browser → Vercel (static React) → Render (FastAPI) → CSV/JSON in repo
```

| Component | Platform | URL example |
|-----------|----------|-------------|
| Frontend | Vercel | `https://finops-guardian.vercel.app` |
| Backend | Render | `https://finops-api.onrender.com` |

---

## 1. Deploy backend (Render)

1. Push this repo to GitHub.
2. [Render Dashboard](https://dashboard.render.com/) → **New** → **Blueprint** (or **Web Service**).
3. Connect the repo and use `render.yaml`, **or** configure manually:

| Setting | Value |
|---------|--------|
| **Root directory** | *(repo root)* |
| **Runtime** | Python 3 |
| **Build command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start command** | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| **Health check path** | `/health` |

4. **Environment variables** (Render → Environment):

| Variable | Value | Required |
|----------|--------|----------|
| `EXECUTION_MODE` | `simulation` | Yes |
| `ALLOW_AWS_SCAN` | `false` | Yes (hosted safety) |
| `MPLBACKEND` | `Agg` | Yes (headless charts) |
| `CORS_ALLOW_ORIGINS` | Your Vercel URL (see step 2) | Yes, after Vercel deploy |
| `GEMINI_API_KEY` | *(optional)* | No |

5. Deploy and copy the service URL, e.g. `https://finops-api.onrender.com`.
6. Verify: `https://finops-api.onrender.com/health` → `{"status":"healthy",...}`

**Notes**

- Free tier **spins down** after ~15 min idle — first request may take 30–60s (cold start).
- **Cloud scan** (synthetic) may be slow or hit timeouts on free tier; the dashboard still loads pre-generated data from the repo.
- **Do not** set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` on Render for a public demo.

---

## 2. Deploy frontend (Vercel)

1. [Vercel Dashboard](https://vercel.com/new) → Import Git repository.
2. **Root Directory** → `frontend`
3. Framework preset: **Vite** (auto-detected via `vercel.json`).
4. **Environment variables**:

| Variable | Value |
|----------|--------|
| `VITE_API_BASE_URL` | `https://finops-api.onrender.com` *(optional; use for a different Render URL, no trailing slash)* |

Without this variable, Vercel proxies `/api/*` to the repository's `finops-api.onrender.com` service. If your Render service has a different hostname, set `VITE_API_BASE_URL` and redeploy the frontend.

5. Deploy and copy the Vercel URL, e.g. `https://finops-guardian.vercel.app`.

6. **Update Render CORS** — go back to Render → Environment:

```
CORS_ALLOW_ORIGINS=https://finops-guardian.vercel.app
```

Multiple origins: comma-separated, no spaces.

7. Redeploy Render (or wait for env reload) and refresh Vercel — Overview should load KPIs.

---

## 3. Verify end-to-end

- [ ] Vercel app loads Overview without API errors
- [ ] Sidebar shows **Synthetic data** (hosted uses bundled outputs)
- [ ] `/health` shows `"deployment":"hosted"` and `"aws_scan_enabled":false`
- [ ] Live Scan dropdown shows **Synthetic only** (AWS hidden on hosted)
- [ ] Approval Center and Executions load
- [ ] `EXECUTION_MODE` remains `simulation` on Render

---

## 4. Local vs hosted

| Feature | Local | Vercel + Render |
|---------|-------|-----------------|
| Live AWS scan | Yes (select a verified Settings account; `ALLOW_AWS_SCAN=true`) | Disabled (`ALLOW_AWS_SCAN=false`) |
| Synthetic scan | Yes | Yes (may be slow on free tier) |
| Real execution | Only if `EXECUTION_MODE=real` | Blocked — keep `simulation` |
| AWS credentials | Encrypted account connection in Settings; `.env` only for standalone CLI use | **Never** on Render |

Keep **Live AWS discovery** on your laptop; use the **hosted URL** for portfolio demos with synthetic data.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| CORS error in browser | Set `CORS_ALLOW_ORIGINS` to exact Vercel URL (https, no trailing slash) |
| API calls go to `localhost` | Set `VITE_API_BASE_URL` on Vercel and redeploy |
| 502 / cold start | Wait 60s; Render free tier waking up |
| Build fails on Prophet | Upgrade to Render Starter or use Docker; ensure Python 3.11 |
| Scan fails on hosted | Expected on free tier — demo still works with committed CSV/JSON |

---

## Optional: custom domains

- Vercel: Project → Settings → Domains
- Render: Service → Settings → Custom Domain
- Add both URLs to `CORS_ALLOW_ORIGINS`
