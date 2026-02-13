"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI } from "@/lib/api";
import type { Meeting } from "@/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MessageSquare } from "lucide-react";

export default function MeetingsPage() {
  const t = useTranslations("meetings");
  const tc = useTranslations("common");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
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
    })();
  }, []);

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "secondary" as const;
      case "running": return "default" as const;
      case "failed": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {loading ? (
        <p className="text-muted-foreground">{tc("loading")}</p>
      ) : meetings.length === 0 ? (
        <div className="text-center py-12">
          <MessageSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">{t("noMeetings")}</p>
          <p className="text-sm text-muted-foreground mt-1">{t("noMeetingsHint")}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {meetings.map((meeting) => (
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
