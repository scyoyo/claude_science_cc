"use client";

import { useEffect, useState, useRef } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { teamsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { Team } from "@/types";
import { Card, CardHeader, CardTitle, CardDescription, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Plus, Trash2, Users, Upload } from "lucide-react";

export default function TeamsPage() {
  const router = useRouter();
  const t = useTranslations("teams");
  const tc = useTranslations("common");
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");

  // Import state
  const [showImport, setShowImport] = useState(false);
  const [importData, setImportData] = useState<Record<string, unknown> | null>(null);
  const [importPreview, setImportPreview] = useState<{ name: string; agentCount: number } | null>(null);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadTeams = async () => {
    try {
      setLoading(true);
      const data = await teamsAPI.list();
      setTeams(data);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load teams"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTeams();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamName.trim()) return;
    try {
      await teamsAPI.create({ name: newTeamName, description: newTeamDesc });
      setNewTeamName("");
      setNewTeamDesc("");
      setShowCreate(false);
      loadTeams();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create team"));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t("deleteConfirm"))) return;
    try {
      await teamsAPI.delete(id);
      loadTeams();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete team"));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const json = JSON.parse(ev.target?.result as string);
        if (!json.name) throw new Error("Missing name");
        setImportData(json);
        setImportPreview({
          name: json.name,
          agentCount: Array.isArray(json.agents) ? json.agents.length : 0,
        });
      } catch {
        setError(t("importError"));
        setImportData(null);
        setImportPreview(null);
      }
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!importData) return;
    setImporting(true);
    try {
      const result = await teamsAPI.importTeam(importData);
      setShowImport(false);
      setImportData(null);
      setImportPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      router.push(`/teams/${result.id}`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to import team"));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <div className="flex gap-2">
          <Dialog open={showImport} onOpenChange={(open) => {
            setShowImport(open);
            if (!open) { setImportData(null); setImportPreview(null); }
          }}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Upload className="h-4 w-4 mr-1" />
                {t("importTeam")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("importTeam")}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept=".json"
                  onChange={handleFileSelect}
                />
                {importPreview && (
                  <div className="p-3 rounded-md bg-muted text-sm">
                    {t("importPreview", { name: importPreview.name, count: importPreview.agentCount })}
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowImport(false)}>
                  {tc("cancel")}
                </Button>
                <Button onClick={handleImport} disabled={!importData || importing}>
                  {t("importConfirm")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-1" />
                {t("create")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("createTeam")}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreate} className="space-y-4">
                <Input
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  placeholder={t("name")}
                  autoFocus
                />
                <Input
                  value={newTeamDesc}
                  onChange={(e) => setNewTeamDesc(e.target.value)}
                  placeholder={t("description")}
                />
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>
                    {tc("cancel")}
                  </Button>
                  <Button type="submit">{t("createTeam")}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-muted-foreground">{tc("loading")}</p>
      ) : teams.length === 0 ? (
        <p className="text-muted-foreground">{t("noTeams")}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {teams.map((team) => (
            <Card
              key={team.id}
              className="hover:border-primary/50 transition-colors cursor-pointer h-full"
              onClick={() => router.push(`/teams/${team.id}`)}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  {team.name}
                </CardTitle>
                {team.description && (
                  <CardDescription className="line-clamp-2">
                    {team.description}
                  </CardDescription>
                )}
                <CardAction>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(team.id);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                </CardAction>
              </CardHeader>
              <div className="px-6 pb-4">
                <span className="text-xs text-muted-foreground">
                  {new Date(team.created_at).toLocaleDateString()}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
