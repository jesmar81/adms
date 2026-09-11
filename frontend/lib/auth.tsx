"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import type { AdminUser } from "@/types";

interface AuthState {
  user: AdminUser | null;
  permissions: string[];
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!api.authenticated) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((me) => {
        setUser(me.user);
        setPermissions(me.permissions);
      })
      .catch(() => api.clearTokens())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const me = await api.login(username, password);
    setUser(me.user);
    setPermissions(me.permissions);
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setUser(null);
    setPermissions([]);
  }, []);

  const can = useCallback((p: string) => permissions.includes(p), [permissions]);
  const value = useMemo(
    () => ({ user, permissions, loading, login, logout, can }),
    [user, permissions, loading, login, logout, can],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

/** Redirects to /login when unauthenticated. Backend remains the enforcer. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);
  if (loading) return <p className="min-h-screen bg-surface-canvas p-8 text-zinc-400">Cargando…</p>;
  if (!user) return null;
  return <>{children}</>;
}

/** Hides UI affordances without the permission (backend still denies). */
export function Can({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth();
  if (!can(permission)) return null;
  return <>{children}</>;
}
