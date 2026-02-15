"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI, teamsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { Meeting, Team } from "@/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageSquare, Search, Trash2, Plus, Loader2, ArrowLeftRight, User, GitMerge } from "lucide-react";
import { NewMeetingDialog } from "@/components/NewMeetingDialog";

type StatusFilter = "all" | "pending" | "completed" | "failed";

export default function MeetingsPage() {
  const t = useTranslations("meetings");
  const tc = useTranslations("common");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [showCreate, setShowCreate] = useState(false);

  const loadMeetings = async () => {
    try {
      setLoading(true);
      const [meetingsData, teamsData] = await Promise.all([
        meetingsAPI.list(),
        teamsAPI.list(),
      ]);
      setMeetings(meetingsData);
      setTeams(teamsData);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load meetings"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMeetings();
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t("deleteConfirm"))) return;
    try {
      await meetingsAPI.delete(id);
      setMeetings((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete meeting"));
    }
  };

  const filtered = meetings.filter((m) => {
    if (statusFilter !== "all" && m.status !== statusFilter) return false;
    if (search && !m.title.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "secondary" as const;
      case "running": return "default" as const;
      case "failed": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  const filterButtons: { key: StatusFilter; label: string }[] = [
    { key: "all", label: t("filterAll") },
    { key: "pending", label: t("filterPending") },
    { key: "completed", label: t("filterCompleted") },
    { key: "failed", label: t("filterFailed") },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/meetings/compare">
              <ArrowLeftRight className="h-4 w-4 mr-1" />
              {t("compareMeetings")}
            </Link>
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4 mr-1" />
            {t("create")}
          </Button>
          <NewMeetingDialog
            open={showCreate}
            onOpenChange={setShowCreate}
            teams={teams}
            onSuccess={() => loadMeetings()}
          />
        </div>
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Search + Filters */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {filterButtons.map((fb) => (
            <Button
              key={fb.key}
              size="sm"
              variant={statusFilter === fb.key ? "default" : "outline"}
              onClick={() => setStatusFilter(fb.key)}
            >
              {fb.label}
            </Button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="text-muted-foreground">{tc("loading")}</p>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12">
          <MessageSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">
            {meetings.length === 0 ? t("noMeetings") : tc("noData")}
          </p>
          {meetings.length === 0 && (
            <p className="text-sm text-muted-foreground mt-1">{t("noMeetingsHint")}</p>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((meeting) => (
            <Card key={meeting.id} className="hover:border-primary/50 transition-colors">
              <CardHeader className="py-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <Link
                    href={`/teams/${meeting.team_id}/meetings/${meeting.id}`}
                    className="flex flex-1 min-w-0 items-center gap-2 cursor-pointer hover:text-primary"
                  >
                    <MessageSquare className="h-4 w-4 shrink-0" />
                    <CardTitle className="text-base truncate">{meeting.title}</CardTitle>
                  </Link>
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    {meeting.meeting_type && meeting.meeting_type !== "team" && (
                      <Badge variant="outline" className="text-xs capitalize">
                        {meeting.meeting_type === "individual" ? <User className="h-3 w-3 mr-1" /> : <GitMerge className="h-3 w-3 mr-1" />}
                        {meeting.meeting_type}
                      </Badge>
                    )}
                    <Badge variant={statusVariant(meeting.status)}>
                      {t(`status.${meeting.status}`)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {t("round", { current: Math.min(meeting.current_round + 1, meeting.max_rounds), max: meeting.max_rounds })}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(meeting.updated_at).toLocaleDateString()}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(e, meeting.id);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
