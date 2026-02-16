"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { artifactsAPI, exportAPI, ApiError } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { downloadBlob } from "@/lib/utils";
import type { CodeArtifact } from "@/types";
import { Button } from "@/components/ui/button";
import FileTree from "@/components/FileTree";
import ArtifactViewer from "@/components/ArtifactViewer";
import { ExportToGithubDialog } from "@/components/ExportToGithubDialog";
import { MarkdownContent } from "@/components/MarkdownContent";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
  FileText,
  BookOpen,
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
  const [pushGithubOpen, setPushGithubOpen] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [exportPreviewOpen, setExportPreviewOpen] = useState(false);
  const [exportPreviewMode, setExportPreviewMode] = useState<"paper" | "blog">("paper");
  const [exportPreviewContent, setExportPreviewContent] = useState("");
  const [exportPreviewTitle, setExportPreviewTitle] = useState("");
  const [exportPreviewLoading, setExportPreviewLoading] = useState(false);

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

  const handleExportPaper = async () => {
    setExportPreviewLoading(true);
    setExportPreviewMode("paper");
    setExportPreviewOpen(true);
    setExportPreviewContent("");
    setExportPreviewTitle(meetingTitle);
    try {
      const data = await exportAPI.paper(meetingId);
      setExportPreviewContent(data.content);
      setExportPreviewTitle(data.title || meetingTitle);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load paper"));
      setExportPreviewContent("");
    } finally {
      setExportPreviewLoading(false);
    }
  };

  const handleExportBlog = async () => {
    setExportPreviewLoading(true);
    setExportPreviewMode("blog");
    setExportPreviewOpen(true);
    setExportPreviewContent("");
    setExportPreviewTitle(meetingTitle);
    try {
      const data = await exportAPI.blog(meetingId);
      setExportPreviewContent(data.content);
      setExportPreviewTitle(data.title || meetingTitle);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load blog"));
      setExportPreviewContent("");
    } finally {
      setExportPreviewLoading(false);
    }
  };

  const handleExportPreviewDownload = () => {
    if (exportPreviewMode === "paper") {
      exportAPI.paperDownload(meetingId, exportPreviewTitle);
    } else {
      exportAPI.blogDownload(meetingId, exportPreviewTitle);
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

      {/* Actions bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Extract Code Dropdown */}
        <Button
          size="sm"
          variant="outline"
          disabled={extracting}
          onClick={handleExtract}
        >
          {extracting ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : (
            <Wand2 className="h-4 w-4 mr-1" />
          )}
          {extracting ? t("extracting") : t("extractArtifacts")}
        </Button>

        {artifacts.length > 0 && (
          <Button size="sm" onClick={handleExportZip} disabled={exporting}>
            {exporting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Archive className="h-4 w-4 mr-1" />}
            {exporting ? t("exporting") : t("exportZip")}
          </Button>
        )}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="outline" disabled={exporting}>
              <Download className="h-4 w-4 mr-1" />
              {t("moreExports")}
              <ChevronDown className="h-3 w-3 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem
              onClick={handleExportNotebook}
              disabled={artifacts.length === 0}
            >
              <FileCode className="h-4 w-4 mr-2" />
              {t("exportNotebook")}
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => setPushGithubOpen(true)}
              disabled={artifacts.length === 0}
            >
              <Upload className="h-4 w-4 mr-2" />
              {t("exportToGithub")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleExportPaper}>
              <FileText className="h-4 w-4 mr-2" />
              {t("exportPaper")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleExportBlog}>
              <BookOpen className="h-4 w-4 mr-2" />
              {t("exportBlog")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
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

      <Dialog open={exportPreviewOpen} onOpenChange={setExportPreviewOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
          <DialogHeader className="shrink-0">
            <DialogTitle>
              {exportPreviewMode === "paper" ? t("exportPaper") : t("exportBlog")}: {exportPreviewTitle}
            </DialogTitle>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-y-auto rounded border p-4 text-sm max-h-[60vh]">
            {exportPreviewLoading ? (
              <p className="text-muted-foreground">{tc("loading")}</p>
            ) : exportPreviewContent ? (
              <MarkdownContent content={exportPreviewContent} className="prose prose-sm dark:prose-invert max-w-none" />
            ) : (
              <p className="text-muted-foreground">{t("noContent")}</p>
            )}
          </div>
          <DialogFooter className="shrink-0">
            <Button variant="outline" onClick={() => setExportPreviewOpen(false)}>
              {tc("close")}
            </Button>
            <Button onClick={handleExportPreviewDownload} disabled={!exportPreviewContent || exportPreviewLoading}>
              <Download className="h-4 w-4 mr-1" />
              {t("downloadExport")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
