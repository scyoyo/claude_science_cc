import type { TokenResponse, User, LoginRequest, RegisterRequest } from "@/types";

const TOKEN_KEY = "vlab_access_token";
const REFRESH_KEY = "vlab_refresh_token";

/** Single source for API base URL (client). Use in auth, api, and pages. */
export function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL || "/api";
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenResponse): void {
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const res = await fetch(`${getApiBase()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Login failed");
  }
  const tokens: TokenResponse = await res.json();
  setTokens(tokens);
  return tokens;
}

export async function register(data: RegisterRequest): Promise<User> {
  const res = await fetch(`${getApiBase()}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Registration failed");
  }
  return res.json();
}

export async function fetchMe(): Promise<User | null> {
  const token = getAccessToken();
  if (!token) return null;

  const res = await fetch(`${getApiBase()}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.ok) return res.json();

  // Try refresh if access token expired
  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      const retry = await fetch(`${getApiBase()}/auth/me`, {
        headers: { Authorization: `Bearer ${getAccessToken()}` },
      });
      if (retry.ok) return retry.json();
    }
  }

  clearTokens();
  return null;
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${getApiBase()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const tokens: TokenResponse = await res.json();
    setTokens(tokens);
    return true;
  } catch {
    return false;
  }
}

export function logout(): void {
  clearTokens();
}
