"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MODEL_OPTIONS, getProviderForModel } from "@/lib/models";
import { useQuotaExhausted } from "@/contexts/QuotaExhaustedContext";
import type { Agent } from "@/types";

export type EditAgentFormData = Pick<
  Agent,
  "name" | "title" | "expertise" | "goal" | "role" | "model" | "system_prompt"
>;

/** Agent (full) or AgentSuggestion (suggestion) — suggestion has no system_prompt. */
export type EditAgentDialogAgent = Omit<EditAgentFormData, "system_prompt"> & { system_prompt?: string };

interface EditAgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agent: EditAgentDialogAgent | null;
  /** Full: team page (includes system_prompt field). Suggestion: onboarding (no system_prompt). Model is always a Select. */
  variant: "full" | "suggestion";
  onSave: (data: EditAgentFormData) => void;
  saving?: boolean;
}

export function EditAgentDialog({
  open,
  onOpenChange,
  agent,
  variant,
  onSave,
  saving = false,
}: EditAgentDialogProps) {
  const t = useTranslations("teamDetail");
  const tc = useTranslations("common");
  const { exhaustedProviders } = useQuotaExhausted();
  const [form, setForm] = useState<EditAgentFormData>({
    name: "",
    title: "",
    expertise: "",
    goal: "",
    role: "",
    model: "gpt-4.1",
    system_prompt: "",
  });

  useEffect(() => {
    if (agent) {
      setForm({
        name: agent.name,
        title: agent.title,
        expertise: agent.expertise,
        goal: agent.goal,
        role: agent.role,
        model: agent.model,
        system_prompt: variant === "full" && "system_prompt" in agent ? (agent.system_prompt ?? "") : "",
      });
    }
  }, [agent, variant, open]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
    onOpenChange(false);
  };

  if (!agent) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto" showCloseButton>
        <DialogHeader>
          <DialogTitle>{t("editAgent")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>{t("agentName")}</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1">
              <Label>{t("agentTitle")}</Label>
              <Input
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                required
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>{t("expertise")}</Label>
            <Input
              value={form.expertise}
              onChange={(e) => setForm((f) => ({ ...f, expertise: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <Label>{t("goal")}</Label>
            <Input
              value={form.goal}
              onChange={(e) => setForm((f) => ({ ...f, goal: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <Label>{t("role")}</Label>
            <Input
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1">
            <Label>{t("model")}</Label>
            <Select
              value={form.model}
              onValueChange={(v) => setForm((f) => ({ ...f, model: v }))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(
                  !form.model || MODEL_OPTIONS.some((o) => o.value === form.model)
                    ? MODEL_OPTIONS
                    : [{ value: form.model, label: form.model }, ...MODEL_OPTIONS]
                ).map((opt) => {
                  const provider = getProviderForModel(opt.value);
                  const exhausted = provider != null && exhaustedProviders.has(provider);
                  return (
                    <SelectItem key={opt.value} value={opt.value} disabled={exhausted}>
                      {opt.label}{exhausted ? ` (${tc("insufficientQuota")})` : ""}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>
          {variant === "full" && (
            <div className="space-y-1">
              <Label>{t("systemPrompt")}</Label>
              <Textarea
                value={form.system_prompt}
                onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
                rows={6}
                className="font-mono text-xs"
              />
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {tc("cancel")}
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? tc("saving") : tc("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
