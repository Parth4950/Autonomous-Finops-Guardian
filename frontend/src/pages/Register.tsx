import { type FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Cloud,
  FlaskConical,
  Lock,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/auth/AuthContext";

export default function RegisterPage() {
  const { user, loading, register, enterSimulationMode } = useAuth();
  const nav = useNavigate();
  const [full_name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register({ full_name, username, email, password });
      nav("/", { replace: true });
    } catch {
      setError(
        "Unable to create account. Check your details or try another email and username."
      );
    } finally {
      setBusy(false);
    }
  }

  function handleLaunchSimulation() {
    enterSimulationMode();
    nav("/", { replace: true });
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4 lg:p-8">
      <div className="w-full max-w-5xl space-y-6">
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
              Autonomous FinOps Guardian
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            AI-Powered Cloud Cost Optimization & Governance
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Choose how you want to enter: explore the interactive 8-stage FinOps pipeline immediately
            in Simulation Mode, or create an account for your isolated personal workspace.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-12">
          {/* Entry Option 1: Simulation Mode */}
          <section className="flex flex-col justify-between rounded-xl border-2 border-primary/40 bg-card p-6 shadow-xl lg:col-span-6 lg:p-8">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge variant="default" className="gap-1.5">
                  <FlaskConical className="h-3.5 w-3.5" />
                  Instant Access · No Login Required
                </Badge>
                <Badge variant="success">Safe Sandbox</Badge>
              </div>

              <div>
                <h2 className="text-xl font-semibold text-foreground">
                  Simulation Mode
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Explore the full dashboard and run synthetic cloud scans immediately without
                  creating an account.
                </p>
              </div>

              <ul className="space-y-2.5 pt-2 text-xs text-muted-foreground">
                <li className="flex items-start gap-2.5">
                  <Radar className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>
                    <strong className="text-foreground">8-Stage FinOps Pipeline:</strong> Run
                    synthetic cloud discovery, waste scoring, and remediation planning on demand.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>
                    <strong className="text-foreground">ML & Forecasting:</strong> Inspect Isolation
                    Forest anomaly detection and 30-day Prophet CPU utilization forecasts.
                  </span>
                </li>
                <li className="flex items-start gap-2.5">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                  <span>
                    <strong className="text-foreground">Isolated Demo Data:</strong> Strictly
                    separated from user workspaces and never touches live AWS infrastructure.
                  </span>
                </li>
              </ul>
            </div>

            <div className="mt-6 space-y-2.5 border-t border-border pt-5">
              <Button
                type="button"
                size="lg"
                className="w-full gap-2 font-semibold"
                onClick={handleLaunchSimulation}
              >
                <FlaskConical className="h-4 w-4" />
                Enter Simulation Mode
                <ArrowRight className="h-4 w-4" />
              </Button>
              <p className="text-center text-[11px] text-muted-foreground">
                No credentials required · Switch to a personal account at any time
              </p>
            </div>
          </section>

          {/* Entry Option 2: Create Personal Workspace Account */}
          <section className="flex flex-col justify-between rounded-xl border border-border bg-card p-6 shadow-xl lg:col-span-6 lg:p-8">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge variant="outline" className="gap-1.5">
                  <Lock className="h-3.5 w-3.5 text-primary" />
                  Personal Workspace
                </Badge>
                <Badge variant="secondary" className="gap-1">
                  <Cloud className="h-3 w-3" />
                  Live AWS Ready
                </Badge>
              </div>

              <div>
                <h2 className="text-xl font-semibold text-foreground">Create Your Account</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Get a dedicated workspace with isolated data, encrypted AWS account storage, and
                  live scanning.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 rounded-lg bg-secondary/60 p-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => nav("/login")}
                >
                  Sign In
                </Button>
                <Button type="button" variant="default" size="sm" className="w-full">
                  Create Account
                </Button>
              </div>

              <form onSubmit={(e) => void submit(e)} className="space-y-3 pt-1">
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="block space-y-1 text-sm">
                    <span className="text-xs font-medium text-muted-foreground">Full Name</span>
                    <Input
                      autoComplete="name"
                      placeholder="Alex Rivera"
                      required
                      maxLength={120}
                      value={full_name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </label>
                  <label className="block space-y-1 text-sm">
                    <span className="text-xs font-medium text-muted-foreground">Username</span>
                    <Input
                      autoComplete="username"
                      placeholder="alex.finops"
                      required
                      minLength={3}
                      maxLength={32}
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                    />
                  </label>
                </div>
                <label className="block space-y-1 text-sm">
                  <span className="text-xs font-medium text-muted-foreground">Email Address</span>
                  <Input
                    type="email"
                    autoComplete="email"
                    placeholder="you@company.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                <label className="block space-y-1 text-sm">
                  <span className="text-xs font-medium text-muted-foreground">
                    Password (12+ characters)
                  </span>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    placeholder="Minimum 12 characters"
                    required
                    minLength={12}
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                {error && (
                  <p role="alert" className="rounded-md border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-400">
                    {error}
                  </p>
                )}
                <Button className="w-full" variant="outline" disabled={busy}>
                  {busy ? "Creating account…" : "Create Personal Workspace"}
                </Button>
              </form>
            </div>

            <p className="mt-4 border-t border-border pt-3 text-center text-xs text-muted-foreground">
              Already registered?{" "}
              <Link className="font-medium text-primary hover:underline" to="/login">
                Sign in to your account
              </Link>
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
