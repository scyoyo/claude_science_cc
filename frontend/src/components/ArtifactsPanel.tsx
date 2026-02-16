"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { artifactsAPI, exportAPI, ApiError } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { downloadBlob } from "@/lib/utils";
import type { CodeArtifact, SmartExtractResponse } from "@/types";
import { Button } from "@/components/ui/button";
import FileTree from "@/components/FileTree";
import ArtifactViewer from "@/components/ArtifactViewer";
import { ExportToGithubDialog } from "@/components/ExportToGithubDialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Download,
  FileCode,
  ChevronDown,
  Wand2,
  Loader2,
  Archive,
  Upload,
  Sparkles,
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
  const [extractingSmart, setExtractingSmart] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewerArtifact, setViewerArtifact] = useState<CodeArtifact | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [pushGithubOpen, setPushGithubOpen] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [smartExtractResult, setSmartExtractResult] = useState<SmartExtractResponse | null>(null);

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
      setSuccessMessage("Code extracted successfully!");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to extract"));
    } finally {
      setExtracting(false);
    }
  };

  const handleExtractSmart = async (model: string = "gpt-4") => {
    try {
      setExtractingSmart(true);
      setError(null);
      setSmartExtractResult(null);

      const result = await artifactsAPI.extractSmart(meetingId, model);
      setSmartExtractResult(result);

      await loadArtifacts();

      // Show success message with project info
      const fileCount = result.files.length;
      const additionalFiles = [];
      if (result.readme_content) additionalFiles.push("README.md");
      if (result.requirements_txt) additionalFiles.push("requirements.txt");
      const totalFiles = fileCount + additionalFiles.length;

      setSuccessMessage(
        `🤖 AI Smart Extract Complete!\n` +
        `Project Type: ${result.project_type}\n` +
        `Files Created: ${totalFiles} (${fileCount} code + ${additionalFiles.length} docs)\n` +
        `Folders: ${result.suggested_folders.join(", ")}`
      );
      setTimeout(() => setSuccessMessage(null), 10000);
    } catch (err) {
      setError(getErrorMessage(err, "AI extraction failed. Try basic extraction instead."));
    } finally {
      setExtractingSmart(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this file?")) return;
    try {
      await artifactsAPI.delete(id);
      setArtifacts((prev) => prev.filter((a) => a.id !== id));
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete"));
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => setSelectedIds(new Set(artifacts.map((a) => a.id)));
  const handleClearSelection = () => setSelectedIds(new Set());

  const handleDeleteSelected = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(t("deleteSelectedConfirm", { count: selectedIds.size }))) return;
    try {
      setError(null);
      for (const id of selectedIds) {
        await artifactsAPI.delete(id);
      }
      await loadArtifacts();
      setSelectedIds(new Set());
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
      setError(err instanceof ApiError && err.status === 400 ? t("extractCodeFirst") : getErrorMessage(err, "Export failed"));
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
      setError(err instanceof ApiError && err.status === 400 ? t("extractCodeFirst") : getErrorMessage(err, "Export failed"));
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
      {successMessage && (
        <div className="p-3 bg-green-500/10 text-green-700 dark:text-green-400 rounded-lg text-sm">
          {successMessage}
        </div>
      )}

      {/* Smart Extract Result Info */}
      {smartExtractResult && (
        <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-950/20 dark:to-blue-950/20 border border-purple-200 dark:border-purple-800 rounded-lg">
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400 mt-0.5 shrink-0" />
            <div className="flex-1 space-y-2 text-sm">
              <div className="font-medium text-purple-900 dark:text-purple-100">
                AI Project Analysis Complete
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted-foreground">
                <div>
                  <span className="font-medium">Project Type:</span>{" "}
                  <span className="capitalize">{smartExtractResult.project_type.replace("_", " ")}</span>
                </div>
                <div>
                  <span className="font-medium">Files Created:</span>{" "}
                  {smartExtractResult.files.length}
                </div>
                {smartExtractResult.suggested_folders.length > 0 && (
                  <div className="sm:col-span-2">
                    <span className="font-medium">Folder Structure:</span>{" "}
                    {smartExtractResult.suggested_folders.join(" / ")}
                  </div>
                )}
                {smartExtractResult.entry_point && (
                  <div className="sm:col-span-2">
                    <span className="font-medium">Entry Point:</span>{" "}
                    <code className="text-xs bg-black/5 dark:bg-white/5 px-1.5 py-0.5 rounded">
                      {smartExtractResult.entry_point}
                    </code>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Actions bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Extract Code Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              size="sm"
              variant="outline"
              disabled={extracting || extractingSmart}
            >
              {extracting ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : extractingSmart ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Wand2 className="h-4 w-4 mr-1" />
              )}
              {extracting ? t("extracting") : extractingSmart ? "AI Extracting..." : t("extractArtifacts")}
              <ChevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem onClick={handleExtract} disabled={extracting || extractingSmart}>
              <Wand2 className="h-4 w-4 mr-2" />
              Quick Extract (Regex)
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => handleExtractSmart("gpt-4")}
              disabled={extracting || extractingSmart}
              className="text-purple-600 dark:text-purple-400"
            >
              <Sparkles className="h-4 w-4 mr-2" />
              🤖 AI Smart Extract (GPT-4)
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => handleExtractSmart("gpt-3.5-turbo")}
              disabled={extracting || extractingSmart}
            >
              <Sparkles className="h-4 w-4 mr-2" />
              AI Extract (GPT-3.5 Fast)
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

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
                  {t("moreExports")}
                  <ChevronDown className="h-3 w-3 ml-1" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={handleExportNotebook}>
                  <FileCode className="h-4 w-4 mr-2" />
                  {t("exportNotebook")}
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setPushGithubOpen(true)}>
                  <Upload className="h-4 w-4 mr-2" />
                  {t("exportToGithub")}
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
          selectedIds={selectedIds}
          onToggleSelect={handleToggleSelect}
          onSelectAll={handleSelectAll}
          onClearSelection={handleClearSelection}
          onDeleteSelected={handleDeleteSelected}
        />
      )}

      <ExportToGithubDialog
        open={pushGithubOpen}
        onOpenChange={setPushGithubOpen}
        meetingId={meetingId}
        meetingTitle={meetingTitle}
        onSuccess={(repoUrl) => {
          setSuccessMessage(`${t("pushSuccess")}: ${repoUrl}`);
          setError(null);
          setTimeout(() => setSuccessMessage(null), 8000);
        }}
      />

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
