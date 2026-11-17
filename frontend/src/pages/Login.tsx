import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/auth/AuthContext";

export default function LoginPage() {
  const { user, loading, login }=useAuth(); const nav=useNavigate(); const loc=useLocation();
  const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  if (!loading && user) return <Navigate to="/" replace/>;
  async function submit(e:FormEvent) { e.preventDefault(); setError(""); setBusy(true); try { await login(email,password); nav(loc.state?.from?.pathname ?? "/",{replace:true}); } catch { setError("Sign-in failed. Check your credentials and try again."); } finally { setBusy(false); } }
  return <main className="flex min-h-screen items-center justify-center bg-background p-4"><section className="w-full max-w-md rounded-xl border border-border bg-card p-8 shadow-xl"><p className="mb-2 text-xs uppercase tracking-[.2em] text-primary">Autonomous FinOps Guardian</p><h1 className="mb-6 text-2xl font-semibold">Welcome back</h1><form onSubmit={submit} className="space-y-4"><label className="block text-sm">Email<Input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="block text-sm">Password<Input type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>{error&&<p role="alert" className="text-sm text-red-400">{error}</p>}<Button className="w-full" disabled={busy}>{busy?"Signing in…":"Sign in"}</Button></form><p className="mt-5 text-sm text-muted-foreground">New here? <Link className="text-primary" to="/register">Create an account</Link></p></section></main>;
}
