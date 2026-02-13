"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { artifactsAPI, exportAPI } from "@/lib/api";
import { downloadBlob } from "@/lib/utils";
import type { CodeArtifact } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Code,
  Download,
  FileCode,
  ChevronDown,
  ChevronRight,
  Wand2,
  Loader2,
  Trash2,
} from "lucide-react";

interface ArtifactsPanelProps {
  meetingId: string;
  meetingTitle: string;
}

export default function ArtifactsPanel({ meetingId, meetingTitle }: ArtifactsPanelProps) {
  const t = useTranslations("meeting");
  const tc = useTranslations("common");
  const [artifacts, setArtifacts] = useState<CodeArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadArtifacts = async () => {
    try {
      setLoading(true);
      const data = await artifactsAPI.listByMeeting(meetingId);
      setArtifacts(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load artifacts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadArtifacts();
  }, [meetingId]);

  const handleExtract = async () => {
    try {
      setExtracting(true);
      setError(null);
      await artifactsAPI.extract(meetingId);
      await loadArtifacts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to extract");
    } finally {
      setExtracting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await artifactsAPI.delete(id);
      setArtifacts((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const handleExportZip = async () => {
    try {
      setExporting(true);
      setError(null);
      const blob = await exportAPI.zip(meetingId);
      downloadBlob(blob, `${meetingTitle.replace(/\s+/g, "_")}.zip`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleExportNotebook = async () => {
    try {
      setExporting(true);
      setError(null);
      const blob = await exportAPI.notebook(meetingId);
      downloadBlob(blob, `${meetingTitle.replace(/\s+/g, "_")}.ipynb`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const handleExportGithub = async () => {
    try {
      setExporting(true);
      setError(null);
      const data = await exportAPI.github(meetingId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      downloadBlob(blob, `${meetingTitle.replace(/\s+/g, "_")}_github.json`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const langColor = (lang: string) => {
    const colors: Record<string, string> = {
      python: "bg-blue-500/10 text-blue-600",
      javascript: "bg-yellow-500/10 text-yellow-600",
      typescript: "bg-blue-600/10 text-blue-700",
      bash: "bg-green-500/10 text-green-600",
      shell: "bg-green-500/10 text-green-600",
    };
    return colors[lang.toLowerCase()] || "";
  };

  if (loading) return <p className="text-muted-foreground text-sm py-4">{tc("loading")}</p>;

  return (
    <div className="space-y-4 py-2">
      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Actions bar */}
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={handleExtract} disabled={extracting}>
          {extracting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Wand2 className="h-4 w-4 mr-1" />}
          {extracting ? t("extracting") : t("extractArtifacts")}
        </Button>

        {artifacts.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button size="sm" variant="outline" disabled={exporting}>
                {exporting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Download className="h-4 w-4 mr-1" />}
                {exporting ? t("exporting") : "Export"}
                <ChevronDown className="h-3 w-3 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem onClick={handleExportZip}>
                <Download className="h-4 w-4 mr-2" />
                {t("exportZip")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExportNotebook}>
                <FileCode className="h-4 w-4 mr-2" />
                {t("exportNotebook")}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExportGithub}>
                <Code className="h-4 w-4 mr-2" />
                {t("exportGithub")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Artifacts list */}
      {artifacts.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("noArtifacts")}</p>
      ) : (
        <div className="space-y-2">
          {artifacts.map((artifact) => (
            <Card key={artifact.id}>
              <CardHeader
                className="py-3 cursor-pointer"
                onClick={() => setExpandedId(expandedId === artifact.id ? null : artifact.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {expandedId === artifact.id ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                    <FileCode className="h-4 w-4 text-muted-foreground" />
                    <CardTitle className="text-sm font-medium">{artifact.filename}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className={langColor(artifact.language)}>
                      {artifact.language}
                    </Badge>
                    <Badge variant="outline" className="text-xs">v{artifact.version}</Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(artifact.id);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {expandedId === artifact.id && (
                <CardContent className="pt-0">
                  {artifact.description && (
                    <p className="text-xs text-muted-foreground mb-2">{artifact.description}</p>
                  )}
                  <ScrollArea className="max-h-80">
                    <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto">
                      <code>{artifact.content}</code>
                    </pre>
                  </ScrollArea>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
