"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI } from "@/lib/api";
import { useMeetingWebSocket, type WSMessage } from "@/hooks/useMeetingWebSocket";
import type { MeetingWithMessages, MeetingMessage } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ArrowLeft, Send, Play, Wifi, WifiOff } from "lucide-react";

export default function MeetingDetailPage() {
  const params = useParams();
  const teamId = params.teamId as string;
  const meetingId = params.meetingId as string;
  const t = useTranslations("meeting");
  const tc = useTranslations("common");

  const [meeting, setMeeting] = useState<MeetingWithMessages | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userMessage, setUserMessage] = useState("");
  const [topic, setTopic] = useState("");
  const [liveMessages, setLiveMessages] = useState<MeetingMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const onWSMessage = useCallback((msg: WSMessage) => {
    if (msg.type === "message" || msg.type === "message_saved") {
      const newMsg: MeetingMessage = {
        id: `live-${Date.now()}-${Math.random()}`,
        meeting_id: meetingId,
        agent_id: msg.agent_id || null,
        role: msg.role || (msg.agent_name ? "assistant" : "user"),
        agent_name: msg.agent_name || null,
        content: msg.content || "",
        round_number: msg.round || 0,
        created_at: new Date().toISOString(),
      };
      setLiveMessages((prev) => [...prev, newMsg]);
      setTimeout(scrollToBottom, 50);
    }
  }, [meetingId, scrollToBottom]);

  const onWSError = useCallback((detail: string) => {
    setError(detail);
    setRunning(false);
  }, []);

  const onRoundComplete = useCallback((round: number, totalRounds: number) => {
    setMeeting((prev) =>
      prev ? { ...prev, current_round: round, status: round >= totalRounds ? "completed" : "pending" } : prev
    );
    setRunning(false);
  }, []);

  const onMeetingComplete = useCallback(() => {
    setMeeting((prev) => (prev ? { ...prev, status: "completed" } : prev));
    setRunning(false);
  }, []);

  const { connected, speaking, connect, disconnect, sendUserMessage, startRound } =
    useMeetingWebSocket({
      meetingId,
      onMessage: onWSMessage,
      onError: onWSError,
      onRoundComplete,
      onMeetingComplete,
    });

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const data = await meetingsAPI.get(meetingId);
        setMeeting(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load meeting");
      } finally {
        setLoading(false);
      }
    })();
  }, [meetingId]);

  useEffect(() => {
    if (meeting && meeting.status !== "completed") {
      connect();
    }
    return () => disconnect();
  }, [meeting?.id, meeting?.status]);

  const handleRunWS = () => {
    if (!connected) return;
    setRunning(true);
    setError(null);
    startRound(1, topic || undefined);
    setTopic("");
  };

  const handleRunHTTP = async () => {
    try {
      setRunning(true);
      setError(null);
      const data = await meetingsAPI.run(meetingId, 1, topic || undefined);
      setMeeting(data);
      setLiveMessages([]);
      setTopic("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run meeting");
    } finally {
      setRunning(false);
    }
  };

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userMessage.trim()) return;

    if (connected) {
      sendUserMessage(userMessage);
    } else {
      meetingsAPI.addMessage(meetingId, userMessage).catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to send")
      );
    }
    setUserMessage("");
  };

  if (loading) return <p className="text-muted-foreground">{tc("loading")}</p>;
  if (!meeting) return <p className="text-destructive">Meeting not found</p>;

  const isCompleted = meeting.status === "completed";
  const allMessages = [...(meeting.messages || []), ...liveMessages];

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "secondary" as const;
      case "running": return "default" as const;
      case "failed": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="shrink-0 space-y-1 mb-4">
        <Link
          href={`/teams/${teamId}`}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("backToTeam")}
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{meeting.title}</h1>
          <Badge variant={statusVariant(meeting.status)}>
            {t(`status.${meeting.status}`)}
          </Badge>
          <span title={connected ? t("wsConnected") : t("wsDisconnected")}>
            {connected ? (
              <Wifi className="h-4 w-4 text-green-500" />
            ) : (
              <WifiOff className="h-4 w-4 text-muted-foreground" />
            )}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {t("round", { current: meeting.current_round, max: meeting.max_rounds })}
        </p>
      </div>

      {error && (
        <div className="shrink-0 p-3 mb-4 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 mb-4">
        <div className="space-y-3 pr-4">
          {allMessages.length === 0 ? (
            <p className="text-muted-foreground text-sm">{t("noMessages")}</p>
          ) : (
            allMessages.map((msg) => (
              <div
                key={msg.id}
                className={`p-4 rounded-lg border ${
                  msg.role === "user"
                    ? "bg-primary/5 border-primary/20"
                    : "bg-card"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">
                    {msg.role === "user" ? t("you") : msg.agent_name || "Assistant"}
                  </span>
                  {msg.round_number > 0 && (
                    <Badge variant="outline" className="text-xs">
                      R{msg.round_number}
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {msg.content}
                </p>
              </div>
            ))
          )}

          {speaking && (
            <div className="p-4 rounded-lg bg-muted border animate-pulse">
              <span className="text-sm text-muted-foreground">
                {t("thinking", { agent: speaking })}
              </span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Controls */}
      {!isCompleted && (
        <div className="shrink-0 space-y-3 border-t pt-4">
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <Input
              value={userMessage}
              onChange={(e) => setUserMessage(e.target.value)}
              placeholder={t("sendMessage")}
              className="flex-1"
            />
            <Button type="submit" size="icon">
              <Send className="h-4 w-4" />
            </Button>
          </form>

          <div className="flex items-center gap-2">
            <Input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={t("topic")}
              className="flex-1"
            />
            <Button
              onClick={connected ? handleRunWS : handleRunHTTP}
              disabled={running}
            >
              <Play className="h-4 w-4 mr-1" />
              {running ? t("running") : connected ? t("runLive") : t("run")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
