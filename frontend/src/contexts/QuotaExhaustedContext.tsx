"use client";

import { createContext, useContext, useCallback, useState, useEffect } from "react";

const STORAGE_KEY = "llm_quota_exhausted_providers";

interface QuotaExhaustedContextType {
  exhaustedProviders: ReadonlySet<string>;
  markExhausted: (provider: string) => void;
  clearExhausted: (provider: string) => void;
  clearAll: () => void;
}

const QuotaExhaustedContext = createContext<QuotaExhaustedContextType | undefined>(undefined);

function loadStored(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function saveStored(set: Set<string>) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
  } catch {
    // ignore
  }
}

export function QuotaExhaustedProvider({ children }: { children: React.ReactNode }) {
  const [set, setSet] = useState<Set<string>>(loadStored);

  useEffect(() => {
    setSet(loadStored());
  }, []);

  const markExhausted = useCallback((provider: string) => {
    if (!provider) return;
    setSet((prev) => {
      const next = new Set(prev);
      next.add(provider);
      saveStored(next);
      return next;
    });
  }, []);

  const clearExhausted = useCallback((provider: string) => {
    setSet((prev) => {
      const next = new Set(prev);
      next.delete(provider);
      saveStored(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setSet(new Set());
    saveStored(new Set());
  }, []);

  const value: QuotaExhaustedContextType = {
    exhaustedProviders: set,
    markExhausted,
    clearExhausted,
    clearAll,
  };

  return (
    <QuotaExhaustedContext.Provider value={value}>
      {children}
    </QuotaExhaustedContext.Provider>
  );
}

export function useQuotaExhausted() {
  const ctx = useContext(QuotaExhaustedContext);
  if (ctx === undefined) throw new Error("useQuotaExhausted must be used within QuotaExhaustedProvider");
  return ctx;
}
