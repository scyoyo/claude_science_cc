"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { artifactsAPI, exportAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { downloadBlob } from "@/lib/utils";
import type { CodeArtifact } from "@/types";
import { Button } from "@/components/ui/button";
import FileTree from "@/components/FileTree";
import ArtifactViewer from "@/components/ArtifactViewer";
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
  Wand2,
  Loader2,
  Archive,
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
  const [error, setError] = useState<string | null>(null);
  const [viewerArtifact, setViewerArtifact] = useState<CodeArtifact | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);

  const loadArtifacts = async () => {
    try {
      setLoading(true);
      const data = await artifactsAPI.listByMeeting(meetingId);
      setArtifacts(data);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load artifacts"));
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
      setError(getErrorMessage(err, "Failed to extract"));
    } finally {
      setExtracting(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this file?")) return;
    try {
      await artifactsAPI.delete(id);
      setArtifacts((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete"));
    }
  };

  const handleViewFile = (artifact: CodeArtifact) => {
    setViewerArtifact(artifact);
    setViewerOpen(true);
  };

  const handleExportZip = async () => {
    try {
      setExporting(true);
      setError(null);
      const blob = await exportAPI.zip(meetingId);
      downloadBlob(blob, `${meetingTitle.replace(/\s+/g, "_")}.zip`);
    } catch (err) {
      setError(getErrorMessage(err, "Export failed"));
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
      setError(getErrorMessage(err, "Export failed"));
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
      setError(getErrorMessage(err, "Export failed"));
    } finally {
      setExporting(false);
    }
  };

  const handleExportJson = async () => {
    try {
      setExporting(true);
      setError(null);
      const blob = await exportAPI.json(meetingId);
      downloadBlob(blob, `${meetingTitle.replace(/\s+/g, "_")}.json`);
    } catch (err) {
      setError(getErrorMessage(err, "Export failed"));
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <p className="text-muted-foreground text-sm py-4">{tc("loading")}</p>;

  return (
    <div className="space-y-4 py-2">
      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Actions bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button size="sm" variant="outline" onClick={handleExtract} disabled={extracting}>
          {extracting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Wand2 className="h-4 w-4 mr-1" />}
          {extracting ? t("extracting") : t("extractArtifacts")}
        </Button>

        {artifacts.length > 0 && (
          <>
            <Button size="sm" onClick={handleExportZip} disabled={exporting}>
              {exporting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Archive className="h-4 w-4 mr-1" />}
              {exporting ? t("exporting") : t("exportZip")}
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" disabled={exporting}>
                  <Download className="h-4 w-4 mr-1" />
                  {t("moreExports") || "More"}
                  <ChevronDown className="h-3 w-3 ml-1" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={handleExportNotebook}>
                  <FileCode className="h-4 w-4 mr-2" />
                  {t("exportNotebook")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleExportGithub}>
                  <Code className="h-4 w-4 mr-2" />
                  {t("exportGithub")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleExportJson}>
                  <FileCode className="h-4 w-4 mr-2" />
                  {t("exportJson")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        )}
      </div>

      {/* File tree */}
      {artifacts.length === 0 ? (
        <p className="text-muted-foreground text-sm">{t("noArtifacts")}</p>
      ) : (
        <FileTree
          artifacts={artifacts}
          onViewFile={handleViewFile}
          onDeleteFile={handleDelete}
        />
      )}

      {/* Artifact viewer */}
      <ArtifactViewer
        artifact={viewerArtifact}
        open={viewerOpen}
        onOpenChange={(open) => {
          setViewerOpen(open);
          if (!open) setViewerArtifact(null);
        }}
      />
    </div>
  );
}
