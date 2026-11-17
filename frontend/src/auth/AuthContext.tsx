import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  apiClient,
  clearCsrfToken,
  isSimulationModeStored,
  setCsrfToken,
  setSimulationModeStored,
} from "@/api/client";
import { queryClient } from "@/lib/queryClient";

export interface AuthUser {
  id: number;
  full_name: string;
  username: string;
  email: string;
  created_at: string;
}

interface AuthState {
  user: AuthUser | null;
  isSimulationMode: boolean;
  loading: boolean;
  enterSimulationMode: () => void;
  exitSimulationMode: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    full_name: string;
    username: string;
    email: string;
    password: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  changePassword: (current_password: string, new_password: string) => Promise<void>;
  updateProfile: (data: {
    full_name?: string;
    username?: string;
    email?: string;
  }) => Promise<AuthUser>;
}

const Context = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isSimulationMode, setIsSimulationMode] = useState<boolean>(() => isSimulationModeStored());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const onExpired = () => {
      clearCsrfToken();
      queryClient.clear();
      setUser(null);
      setLoading(false);
    };
    window.addEventListener("auth:expired", onExpired);

    if (isSimulationModeStored()) {
      setUser(null);
      setIsSimulationMode(true);
      setLoading(false);
      return () => window.removeEventListener("auth:expired", onExpired);
    }

    apiClient
      .get<AuthUser>("/auth/me")
      .then((r) => {
        setSimulationModeStored(false);
        setIsSimulationMode(false);
        setUser(r.data);
      })
      .catch(() => {
        queryClient.clear();
        setUser(null);
      })
      .finally(() => setLoading(false));

    return () => window.removeEventListener("auth:expired", onExpired);
  }, []);

  const enterSimulationMode = useCallback(() => {
    clearCsrfToken();
    queryClient.clear();
    setUser(null);
    setSimulationModeStored(true);
    setIsSimulationMode(true);
  }, []);

  const exitSimulationMode = useCallback(() => {
    clearCsrfToken();
    queryClient.clear();
    setSimulationModeStored(false);
    setIsSimulationMode(false);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      isSimulationMode,
      loading,
      enterSimulationMode,
      exitSimulationMode,
      async login(email, password) {
        setSimulationModeStored(false);
        setIsSimulationMode(false);
        const { data } = await apiClient.post<{ user: AuthUser; csrf_token: string }>(
          "/auth/login",
          { email, password }
        );
        queryClient.clear();
        setCsrfToken(data.csrf_token);
        setUser(data.user);
      },
      async register(data) {
        setSimulationModeStored(false);
        setIsSimulationMode(false);
        const response = await apiClient.post<{ user: AuthUser; csrf_token: string }>(
          "/auth/register",
          data
        );
        queryClient.clear();
        setCsrfToken(response.data.csrf_token);
        setUser(response.data.user);
      },
      async logout() {
        try {
          if (user) {
            await apiClient.post("/auth/logout");
          }
        } finally {
          clearCsrfToken();
          setSimulationModeStored(false);
          setIsSimulationMode(false);
          queryClient.clear();
          setUser(null);
        }
      },
      async logoutAll() {
        try {
          if (user) {
            await apiClient.post("/auth/logout-all");
          }
        } finally {
          clearCsrfToken();
          setSimulationModeStored(false);
          setIsSimulationMode(false);
          queryClient.clear();
          setUser(null);
        }
      },
      async changePassword(current_password, new_password) {
        await apiClient.post("/auth/change-password", { current_password, new_password });
        clearCsrfToken();
        setSimulationModeStored(false);
        setIsSimulationMode(false);
        queryClient.clear();
        setUser(null);
      },
      async updateProfile(data) {
        const response = await apiClient.patch<AuthUser>("/auth/profile", data);
        setUser(response.data);
        return response.data;
      },
    }),
    [user, isSimulationMode, loading, enterSimulationMode, exitSimulationMode]
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
