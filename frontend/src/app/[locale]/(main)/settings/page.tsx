"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Trash2, Plus, Key } from "lucide-react";

const API_BASE =
  typeof window !== "undefined"
    ? "/api"
    : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api");

interface APIKeyInfo {
  id: string;
  provider: string;
  is_active: boolean;
  key_preview: string;
  created_at: string;
}

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tc = useTranslations("common");
  const [keys, setKeys] = useState<APIKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");

  const loadKeys = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/llm/api-keys`);
      if (!res.ok) throw new Error("Failed to load API keys");
      setKeys(await res.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/llm/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to add key");
      }
      setApiKey("");
      loadKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add key");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`${API_BASE}/llm/api-keys/${id}`, { method: "DELETE" });
      loadKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete key");
    }
  };

  return (
    <div className="space-y-8 max-w-2xl">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            {t("apiKeys")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleAdd} className="flex gap-3">
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="openai">OpenAI</SelectItem>
                <SelectItem value="anthropic">Anthropic</SelectItem>
                <SelectItem value="deepseek">DeepSeek</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("apiKeyPlaceholder")}
              className="flex-1"
            />
            <Button type="submit" size="sm">
              <Plus className="h-4 w-4 mr-1" />
              {t("addKey")}
            </Button>
          </form>

          {loading ? (
            <p className="text-muted-foreground">{tc("loading")}</p>
          ) : keys.length === 0 ? (
            <p className="text-muted-foreground text-sm">{t("noKeys")}</p>
          ) : (
            <div className="space-y-2">
              {keys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium capitalize">{key.provider}</span>
                    <span className="text-sm text-muted-foreground">{key.key_preview}</span>
                    {!key.is_active && (
                      <Badge variant="destructive">{t("inactive")}</Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    onClick={() => handleDelete(key.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
