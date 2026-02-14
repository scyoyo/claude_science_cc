"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { meetingsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { MeetingSummary } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Users, MessageSquare, RotateCw, Lightbulb } from "lucide-react";

interface MeetingSummaryPanelProps {
  meetingId: string;
}

export default function MeetingSummaryPanel({ meetingId }: MeetingSummaryPanelProps) {
  const t = useTranslations("meeting");
  const tc = useTranslations("common");
  const [summary, setSummary] = useState<MeetingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const data = await meetingsAPI.summary(meetingId);
        setSummary(data);
        setError(null);
      } catch (err) {
        setError(getErrorMessage(err, "Failed to load summary"));
      } finally {
        setLoading(false);
      }
    })();
  }, [meetingId]);

  if (loading) return <p className="text-muted-foreground text-sm py-4">{tc("loading")}</p>;
  if (error) return <p className="text-destructive text-sm py-4">{error}</p>;
  if (!summary || (summary.total_messages === 0)) {
    return <p className="text-muted-foreground text-sm py-4">{t("noSummary")}</p>;
  }

  return (
    <div className="space-y-4 py-2">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">{t("summaryTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Stats row */}
          <div className="flex gap-6">
            <div className="flex items-center gap-2 text-sm">
              <RotateCw className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{t("totalRounds")}:</span>
              <span className="font-medium">{summary.total_rounds}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <MessageSquare className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{t("totalMessages")}:</span>
              <span className="font-medium">{summary.total_messages}</span>
            </div>
          </div>

          <Separator />

          {/* Participants */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">{t("participants")}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {summary.participants.map((name) => (
                <Badge key={name} variant="secondary">{name}</Badge>
              ))}
              {summary.participants.length === 0 && (
                <span className="text-sm text-muted-foreground">-</span>
              )}
            </div>
          </div>

          <Separator />

          {/* Key Points */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">{t("keyPoints")}</span>
            </div>
            {summary.key_points.length > 0 ? (
              <ul className="space-y-2">
                {summary.key_points.map((point, i) => (
                  <li key={i} className="text-sm text-muted-foreground pl-4 border-l-2 border-muted">
                    {point}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">{t("noKeyPoints")}</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
