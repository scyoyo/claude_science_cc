"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { templatesAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { AgentTemplate } from "@/types";
import { getModelLabel } from "@/lib/models";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus } from "lucide-react";

const CATEGORIES = ["All", "AI/ML", "Biology", "Chemistry", "General"];

interface TemplatesBrowserProps {
  teamId: string;
  onApplied: () => void;
}

export default function TemplatesBrowser({ teamId, onApplied }: TemplatesBrowserProps) {
  const t = useTranslations("templates");
  const tc = useTranslations("common");

  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState<string | null>(null);
  const [category, setCategory] = useState("All");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    templatesAPI.list().then((data) => {
      setTemplates(data);
      setLoading(false);
    }).catch((err) => {
      setError(getErrorMessage(err, "Failed to load templates"));
      setLoading(false);
    });
  }, []);

  const handleApply = async (templateId: string) => {
    setApplying(templateId);
    try {
      await templatesAPI.apply(templateId, teamId);
      onApplied();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to apply template"));
    } finally {
      setApplying(null);
    }
  };

  const filtered = category === "All"
    ? templates
    : templates.filter((t) => t.category === category);

  if (loading) return <p className="text-muted-foreground py-4">{tc("loading")}</p>;

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Category tabs */}
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map((cat) => (
          <Button
            key={cat}
            size="sm"
            variant={category === cat ? "default" : "outline"}
            onClick={() => setCategory(cat)}
          >
            {cat === "All" ? t("all") : cat}
          </Button>
        ))}
      </div>

      {/* Template cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[400px] overflow-y-auto">
        {filtered.map((tmpl) => (
          <Card key={tmpl.id} className="flex flex-col">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">{tmpl.name}</CardTitle>
                <Badge variant="outline" className="text-[10px] shrink-0">{getModelLabel(tmpl.model)}</Badge>
              </div>
              <CardDescription className="text-xs">{tmpl.title}</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col justify-between gap-3">
              <p className="text-xs text-muted-foreground line-clamp-2">{tmpl.expertise}</p>
              <Button
                size="sm"
                variant="outline"
                className="w-full"
                disabled={applying === tmpl.id}
                onClick={() => handleApply(tmpl.id)}
              >
                {applying === tmpl.id ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5 mr-1" />
                )}
                {applying === tmpl.id ? t("adding") : t("addToTeam")}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
