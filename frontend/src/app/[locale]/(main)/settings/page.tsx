"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Trash2, Plus, Key, Webhook, Pencil, Loader2 } from "lucide-react";
import { llmAPI, webhooksAPI, type APIKeyInfo } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { useQuotaExhausted } from "@/contexts/QuotaExhaustedContext";
import type { Webhook as WebhookType } from "@/types";

const WEBHOOK_EVENTS = [
  "meeting.completed",
  "meeting.failed",
  "artifact.created",
  "team.created",
  "agent.created",
];

export default function SettingsPage() {
  const t = useTranslations("settings");
  const tw = useTranslations("webhooks");
  const tc = useTranslations("common");
  const { clearExhausted } = useQuotaExhausted();
  const [keys, setKeys] = useState<APIKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");

  // Webhooks state
  const [webhooks, setWebhooks] = useState<WebhookType[]>([]);
  const [webhooksLoading, setWebhooksLoading] = useState(true);
  const [showAddWebhook, setShowAddWebhook] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookType | null>(null);
  const [webhookForm, setWebhookForm] = useState({ url: "", events: [] as string[], secret: "" });
  const [savingWebhook, setSavingWebhook] = useState(false);

  const loadKeys = async () => {
    try {
      setLoading(true);
      setKeys(await llmAPI.listKeys());
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load"));
    } finally {
      setLoading(false);
    }
  };

  const loadWebhooks = async () => {
    try {
      setWebhooksLoading(true);
      setWebhooks(await webhooksAPI.list());
    } catch {
      // silently fail — webhooks are optional
    } finally {
      setWebhooksLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
    loadWebhooks();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    try {
      await llmAPI.addKey(provider, apiKey);
      clearExhausted(provider);
      setApiKey("");
      loadKeys();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to add key"));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await llmAPI.deleteKey(id);
      setKeys((prev) => prev.filter((k) => k.id !== id));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete key"));
    }
  };

  // Webhook handlers
  const resetWebhookForm = () => {
    setWebhookForm({ url: "", events: [], secret: "" });
    setEditingWebhook(null);
  };

  const toggleEvent = (event: string) => {
    setWebhookForm((f) => ({
      ...f,
      events: f.events.includes(event)
        ? f.events.filter((e) => e !== event)
        : [...f.events, event],
    }));
  };

  const handleSaveWebhook = async () => {
    if (!webhookForm.url.trim() || webhookForm.events.length === 0) return;
    setSavingWebhook(true);
    try {
      if (editingWebhook) {
        await webhooksAPI.update(editingWebhook.id, {
          url: webhookForm.url,
          events: webhookForm.events,
        });
      } else {
        await webhooksAPI.create({
          url: webhookForm.url,
          events: webhookForm.events,
          secret: webhookForm.secret || undefined,
        });
      }
      setShowAddWebhook(false);
      resetWebhookForm();
      await loadWebhooks();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to save webhook"));
    } finally {
      setSavingWebhook(false);
    }
  };

  const handleEditWebhook = (wh: WebhookType) => {
    setEditingWebhook(wh);
    setWebhookForm({ url: wh.url, events: [...wh.events], secret: "" });
    setShowAddWebhook(true);
  };

  const handleToggleWebhook = async (wh: WebhookType) => {
    try {
      await webhooksAPI.update(wh.id, { is_active: !wh.is_active });
      await loadWebhooks();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to toggle webhook"));
    }
  };

  const handleDeleteWebhook = async (id: string) => {
    if (!confirm(tw("deleteConfirm"))) return;
    try {
      await webhooksAPI.delete(id);
      setWebhooks((prev) => prev.filter((w) => w.id !== id));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete webhook"));
    }
  };

  return (
    <div className="space-y-8 max-w-2xl">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* API Keys Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            {t("apiKeys")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleAdd} className="flex flex-col sm:flex-row gap-3">
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="sm:w-[140px]">
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

      {/* Webhooks Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Webhook className="h-5 w-5" />
              {tw("title")}
            </CardTitle>
            <Dialog
              open={showAddWebhook}
              onOpenChange={(open) => {
                setShowAddWebhook(open);
                if (!open) resetWebhookForm();
              }}
            >
              <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                  <Plus className="h-4 w-4 mr-1" />
                  {tw("addWebhook")}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>
                    {editingWebhook ? tw("editWebhook") : tw("addWebhook")}
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div className="space-y-2">
                    <Label>{tw("url")}</Label>
                    <Input
                      value={webhookForm.url}
                      onChange={(e) => setWebhookForm((f) => ({ ...f, url: e.target.value }))}
                      placeholder={tw("urlPlaceholder")}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{tw("events")}</Label>
                    <div className="flex flex-wrap gap-2">
                      {WEBHOOK_EVENTS.map((event) => (
                        <label key={event} className="flex items-center gap-1.5 text-sm cursor-pointer">
                          <input
                            type="checkbox"
                            checked={webhookForm.events.includes(event)}
                            onChange={() => toggleEvent(event)}
                            className="rounded"
                          />
                          <span>{event}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  {!editingWebhook && (
                    <div className="space-y-2">
                      <Label>{tw("secret")}</Label>
                      <Input
                        type="password"
                        value={webhookForm.secret}
                        onChange={(e) => setWebhookForm((f) => ({ ...f, secret: e.target.value }))}
                        placeholder={tw("secret")}
                      />
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => { setShowAddWebhook(false); resetWebhookForm(); }}
                  >
                    {tc("cancel")}
                  </Button>
                  <Button
                    onClick={handleSaveWebhook}
                    disabled={savingWebhook || !webhookForm.url.trim() || webhookForm.events.length === 0}
                  >
                    {savingWebhook && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                    {tc("save")}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          {webhooksLoading ? (
            <p className="text-muted-foreground">{tc("loading")}</p>
          ) : webhooks.length === 0 ? (
            <p className="text-muted-foreground text-sm">{tw("noWebhooks")}</p>
          ) : (
            <div className="space-y-2">
              {webhooks.map((wh) => (
                <div
                  key={wh.id}
                  className="flex items-center justify-between p-3 rounded-lg border"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">{wh.url}</span>
                      <Badge variant={wh.is_active ? "secondary" : "outline"} className="shrink-0">
                        {wh.is_active ? tw("active") : tw("inactive")}
                      </Badge>
                    </div>
                    <div className="flex gap-1 mt-1 flex-wrap">
                      {wh.events.map((ev) => (
                        <Badge key={ev} variant="outline" className="text-[10px]">{ev}</Badge>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleToggleWebhook(wh)}
                      title={wh.is_active ? tw("inactive") : tw("active")}
                    >
                      <span className={`h-2 w-2 rounded-full ${wh.is_active ? "bg-green-500" : "bg-gray-400"}`} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleEditWebhook(wh)}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleDeleteWebhook(wh.id)}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
