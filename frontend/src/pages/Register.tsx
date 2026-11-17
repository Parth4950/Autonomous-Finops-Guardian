import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/auth/AuthContext";

export default function RegisterPage() {
  const {user,loading,register}=useAuth(); const nav=useNavigate(); const [full_name,setName]=useState(""); const [username,setUsername]=useState(""); const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  if (!loading&&user) return <Navigate to="/" replace/>;
  async function submit(e:FormEvent) { e.preventDefault(); setError("");setBusy(true);try{await register({full_name,username,email,password});nav("/",{replace:true});}catch{setError("Unable to create account. Check your details or try another email and username.");}finally{setBusy(false);} }
  return <main className="flex min-h-screen items-center justify-center bg-background p-4"><section className="w-full max-w-md rounded-xl border border-border bg-card p-8 shadow-xl"><p className="mb-2 text-xs uppercase tracking-[.2em] text-primary">Autonomous FinOps Guardian</p><h1 className="mb-6 text-2xl font-semibold">Create your account</h1><form onSubmit={submit} className="space-y-3"><label className="block text-sm">Full name<Input autoComplete="name" required maxLength={120} value={full_name} onChange={e=>setName(e.target.value)}/></label><label className="block text-sm">Username<Input autoComplete="username" required minLength={3} maxLength={32} value={username} onChange={e=>setUsername(e.target.value)}/></label><label className="block text-sm">Email<Input type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="block text-sm">Password (12+ characters)<Input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={e=>setPassword(e.target.value)}/></label>{error&&<p role="alert" className="text-sm text-red-400">{error}</p>}<Button className="w-full" disabled={busy}>{busy?"Creating account…":"Create account"}</Button></form><p className="mt-5 text-sm text-muted-foreground">Already registered? <Link className="text-primary" to="/login">Sign in</Link></p></section></main>;
}
