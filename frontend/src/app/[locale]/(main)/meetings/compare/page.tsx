"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { meetingsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { Meeting, MeetingComparison } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeftRight, Loader2 } from "lucide-react";

export default function CompareMeetingsPage() {
  const t = useTranslations("comparison");
  const tc = useTranslations("common");

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [firstId, setFirstId] = useState("");
  const [secondId, setSecondId] = useState("");
  const [comparing, setComparing] = useState(false);
  const [result, setResult] = useState<MeetingComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    meetingsAPI.list().then((all) => {
      setMeetings(all.filter((m) => m.status === "completed"));
      setLoading(false);
    }).catch((err) => {
      setError(getErrorMessage(err, "Failed to load meetings"));
      setLoading(false);
    });
  }, []);

  const handleCompare = async () => {
    if (!firstId || !secondId || firstId === secondId) return;
    setComparing(true);
    setError(null);
    try {
      const data = await meetingsAPI.compare(firstId, secondId);
      setResult(data);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to compare"));
    } finally {
      setComparing(false);
    }
  };

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "secondary" as const;
      case "running": return "default" as const;
      case "failed": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  if (loading) return <p className="text-muted-foreground">{tc("loading")}</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {meetings.length < 2 ? (
        <p className="text-muted-foreground">{t("noCompletedMeetings")}</p>
      ) : (
        <>
          <div className="flex flex-col sm:flex-row gap-3 items-end">
            <div className="flex-1 space-y-1">
              <label className="text-sm font-medium">{t("selectFirst")}</label>
              <Select value={firstId} onValueChange={setFirstId}>
                <SelectTrigger>
                  <SelectValue placeholder={t("selectFirst")} />
                </SelectTrigger>
                <SelectContent>
                  {meetings.map((m) => (
                    <SelectItem key={m.id} value={m.id} disabled={m.id === secondId}>
                      {m.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <ArrowLeftRight className="h-5 w-5 text-muted-foreground shrink-0 hidden sm:block" />

            <div className="flex-1 space-y-1">
              <label className="text-sm font-medium">{t("selectSecond")}</label>
              <Select value={secondId} onValueChange={setSecondId}>
                <SelectTrigger>
                  <SelectValue placeholder={t("selectSecond")} />
                </SelectTrigger>
                <SelectContent>
                  {meetings.map((m) => (
                    <SelectItem key={m.id} value={m.id} disabled={m.id === firstId}>
                      {m.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              onClick={handleCompare}
              disabled={comparing || !firstId || !secondId || firstId === secondId}
              className="shrink-0"
            >
              {comparing && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              {t("compareButton")}
            </Button>
          </div>

          {!result && !comparing && (
            <p className="text-sm text-muted-foreground">{t("selectBoth")}</p>
          )}

          {result && (
            <div className="space-y-6">
              {/* Side-by-side comparison */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.meetings.map((m) => (
                  <Card key={m.id}>
                    <CardHeader>
                      <CardTitle className="text-base">{m.title}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Status</span>
                        <Badge variant={statusVariant(m.status)}>{m.status}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">{t("rounds")}</span>
                        <span>{m.rounds}/{m.max_rounds}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">{t("messages")}</span>
                        <span>{m.message_count}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">{t("participants")}</span>
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {m.participants.map((p) => (
                            <Badge key={p} variant="outline" className="text-xs">{p}</Badge>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Participant analysis */}
              <Card>
                <CardContent className="py-4 space-y-3">
                  {result.shared_participants.length > 0 && (
                    <div>
                      <span className="text-sm font-medium">{t("sharedParticipants")}: </span>
                      {result.shared_participants.map((p) => (
                        <Badge key={p} variant="secondary" className="mr-1 text-xs">{p}</Badge>
                      ))}
                    </div>
                  )}
                  {result.unique_to_first.length > 0 && (
                    <div>
                      <span className="text-sm font-medium">{t("uniqueToFirst")}: </span>
                      {result.unique_to_first.map((p) => (
                        <Badge key={p} variant="outline" className="mr-1 text-xs">{p}</Badge>
                      ))}
                    </div>
                  )}
                  {result.unique_to_second.length > 0 && (
                    <div>
                      <span className="text-sm font-medium">{t("uniqueToSecond")}: </span>
                      {result.unique_to_second.map((p) => (
                        <Badge key={p} variant="outline" className="mr-1 text-xs">{p}</Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}
