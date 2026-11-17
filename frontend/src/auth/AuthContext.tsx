import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiClient, clearCsrfToken, setCsrfToken } from "@/api/client";
import { queryClient } from "@/lib/queryClient";

export interface AuthUser { id: number; full_name: string; username: string; email: string; created_at: string }
interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {full_name:string;username:string;email:string;password:string}) => Promise<void>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  changePassword: (current_password: string, new_password: string) => Promise<void>;
  updateProfile: (data: { full_name?: string; username?: string; email?: string }) => Promise<AuthUser>;
}
const Context = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const onExpired = () => { clearCsrfToken(); queryClient.clear(); setUser(null); setLoading(false); };
    window.addEventListener("auth:expired", onExpired);
    apiClient.get<AuthUser>("/auth/me").then(r => setUser(r.data)).catch(() => { queryClient.clear(); setUser(null); }).finally(() => setLoading(false));
    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);
  const value = useMemo<AuthState>(() => ({
    user, loading,
    async login(email, password) { const {data}=await apiClient.post<{user:AuthUser;csrf_token:string}>("/auth/login",{email,password}); queryClient.clear(); setCsrfToken(data.csrf_token); setUser(data.user); },
    async register(data) { const response=await apiClient.post<{user:AuthUser;csrf_token:string}>("/auth/register",data); queryClient.clear(); setCsrfToken(response.data.csrf_token); setUser(response.data.user); },
    async logout() { try { await apiClient.post("/auth/logout"); } finally { clearCsrfToken(); queryClient.clear(); setUser(null); } },
    async logoutAll() { try { await apiClient.post("/auth/logout-all"); } finally { clearCsrfToken(); queryClient.clear(); setUser(null); } },
    async changePassword(current_password, new_password) { await apiClient.post("/auth/change-password", { current_password, new_password }); clearCsrfToken(); queryClient.clear(); setUser(null); },
    async updateProfile(data) { const response = await apiClient.patch<AuthUser>("/auth/profile", data); setUser(response.data); return response.data; },
  }), [user, loading]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAuth() { const value=useContext(Context); if (!value) throw new Error("AuthProvider is missing"); return value; }
