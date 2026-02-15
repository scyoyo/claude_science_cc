"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { exportAPI, ApiError } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
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
import { Loader2 } from "lucide-react";

interface ExportToGithubDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  meetingId: string;
  onSuccess?: (repoUrl: string) => void;
}

export function ExportToGithubDialog({
  open,
  onOpenChange,
  meetingId,
  onSuccess,
}: ExportToGithubDialogProps) {
  const t = useTranslations("meeting");
  const tc = useTranslations("common");
  const [repoOwner, setRepoOwner] = useState("");
  const [repoName, setRepoName] = useState("");
  const [createIfMissing, setCreateIfMissing] = useState(false);
  const [githubToken, setGithubToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoOwner.trim() || !repoName.trim() || !githubToken.trim()) {
      setError("Please fill owner, repository name, and token.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const result = await exportAPI.pushGithub(meetingId, {
        repo_owner: repoOwner.trim(),
        repo_name: repoName.trim(),
        create_if_missing: createIfMissing,
        github_token: githubToken.trim(),
      });
      onSuccess?.(result.repo_url);
      onOpenChange(false);
      setRepoOwner("");
      setRepoName("");
      setGithubToken("");
    } catch (err) {
      const msg =
        err instanceof ApiError && err.body?.detail
          ? String(err.body.detail)
          : getErrorMessage(err, "Push failed");
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("pushToGithubTitle")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-destructive/10 text-destructive text-sm p-3">{error}</div>
          )}
          <div>
            <Label htmlFor="push-owner">{t("repoOwner")}</Label>
            <Input
              id="push-owner"
              value={repoOwner}
              onChange={(e) => setRepoOwner(e.target.value)}
              placeholder="username or org"
              className="mt-1"
              autoComplete="off"
            />
          </div>
          <div>
            <Label htmlFor="push-repo">{t("repoName")}</Label>
            <Input
              id="push-repo"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
              placeholder="my-repo"
              className="mt-1"
              autoComplete="off"
            />
          </div>
          <div>
            <Label htmlFor="push-token">{t("githubToken")}</Label>
            <Input
              id="push-token"
              type="password"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
              placeholder={t("githubTokenPlaceholder")}
              className="mt-1"
              autoComplete="off"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="push-create"
              checked={createIfMissing}
              onChange={(e) => setCreateIfMissing(e.target.checked)}
              className="rounded border-input"
            />
            <Label htmlFor="push-create" className="font-normal cursor-pointer">
              {t("createIfMissing")}
            </Label>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              {tc("cancel")}
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              {submitting ? t("exporting") : t("pushToGithub")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
