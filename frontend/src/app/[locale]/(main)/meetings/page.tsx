"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI } from "@/lib/api";
import type { Meeting } from "@/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageSquare, Search, Trash2 } from "lucide-react";

type StatusFilter = "all" | "pending" | "completed" | "failed";

export default function MeetingsPage() {
  const t = useTranslations("meetings");
  const tc = useTranslations("common");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const loadMeetings = async () => {
    try {
      setLoading(true);
      const data = await meetingsAPI.list();
      setMeetings(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load meetings");
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
      setError(err instanceof Error ? err.message : "Failed to delete meeting");
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
      <h1 className="text-2xl font-bold">{t("title")}</h1>

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
        <div className="flex gap-2">
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
            <Link
              key={meeting.id}
              href={`/teams/${meeting.team_id}/meetings/${meeting.id}`}
            >
              <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                <CardHeader className="py-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <MessageSquare className="h-4 w-4" />
                      {meeting.title}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge variant={statusVariant(meeting.status)}>
                        {t(`status.${meeting.status}`)}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {t("round", { current: meeting.current_round, max: meeting.max_rounds })}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(meeting.updated_at).toLocaleDateString()}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => handleDelete(e, meeting.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
