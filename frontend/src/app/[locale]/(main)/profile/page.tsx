"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { getAuthHeaders } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const t = useTranslations("profile");
  const tc = useTranslations("common");
  const ta = useTranslations("auth");
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) return <p className="text-muted-foreground">{tc("loading")}</p>;

  if (!user) {
    router.push("/login");
    return null;
  }

  function startEdit() {
    setEmail(user!.email);
    setUsername(user!.username);
    setPassword("");
    setEditing(true);
    setError("");
    setSuccess("");
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    const body: Record<string, string> = {};
    if (email !== user!.email) body.email = email;
    if (username !== user!.username) body.username = username;
    if (password) body.password = password;

    if (Object.keys(body).length === 0) {
      setEditing(false);
      setSubmitting(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Update failed");
      }
      setSuccess(t("updated"));
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}
      {success && (
        <div className="p-3 bg-green-500/10 text-green-700 dark:text-green-400 rounded-lg text-sm">{success}</div>
      )}

      <Card>
        <CardContent className="pt-6">
          {!editing ? (
            <div className="space-y-4">
              <div>
                <Label className="text-muted-foreground">{t("username")}</Label>
                <p className="font-medium">{user.username}</p>
              </div>
              <div>
                <Label className="text-muted-foreground">{t("email")}</Label>
                <p>{user.email}</p>
              </div>
              <div>
                <Label className="text-muted-foreground">{t("role")}</Label>
                <div className="mt-1">
                  <Badge variant="secondary">
                    {user.is_admin ? t("admin") : t("user")}
                  </Badge>
                </div>
              </div>
              <div>
                <Label className="text-muted-foreground">{t("memberSince")}</Label>
                <p>{new Date(user.created_at).toLocaleDateString()}</p>
              </div>
              <div className="flex gap-3 pt-2">
                <Button onClick={startEdit} size="sm">
                  {t("editProfile")}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    logout();
                    router.push("/login");
                  }}
                >
                  {ta("logout")}
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSave} className="space-y-4">
              <div className="space-y-2">
                <Label>{t("email")}</Label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("username")}</Label>
                <Input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  minLength={3}
                  pattern="^[a-zA-Z0-9_-]+$"
                />
              </div>
              <div className="space-y-2">
                <Label>{t("changePassword")}</Label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  placeholder={ta("passwordMin")}
                />
              </div>
              <div className="flex gap-3">
                <Button type="submit" disabled={submitting} size="sm">
                  {submitting ? t("saving") : t("update")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(false)}
                >
                  {tc("cancel")}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
