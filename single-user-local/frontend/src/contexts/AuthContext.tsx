"use client";

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import type { User, LoginRequest, RegisterRequest } from "@/types";
import * as authLib from "@/lib/auth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authLib.fetchMe().then((u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  const login = useCallback(async (data: LoginRequest) => {
    await authLib.login(data);
    const u = await authLib.fetchMe();
    setUser(u);
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    await authLib.register(data);
    // Auto-login after registration
    await authLib.login({ username: data.username, password: data.password });
    const u = await authLib.fetchMe();
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    authLib.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
