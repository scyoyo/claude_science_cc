"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI, agendaAPI, agentsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { useMeetingPolling } from "@/hooks/useMeetingPolling";
import { downloadBlob } from "@/lib/utils";
import { useMeetingWebSocket, type WSMessage } from "@/hooks/useMeetingWebSocket";
import type { Meeting, MeetingWithMessages, MeetingMessage, Agent } from "@/types";
import MeetingSummaryPanel from "@/components/MeetingSummaryPanel";
import ArtifactsPanel from "@/components/ArtifactsPanel";
import { MarkdownContent } from "@/components/MarkdownContent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
  ArrowLeft,
  Send,
  Play,
  PlayCircle,
  Wifi,
  WifiOff,
  CopyPlus,
  FileDown,
  MoreVertical,
  Pencil,
  Trash2,
  Loader2,
  MessageSquare,
  BarChart3,
  Code,
  RefreshCw,
  Layers,
  User,
  GitMerge,
} from "lucide-react";

export default function MeetingDetailPage() {
  const params = useParams();
  const router = useRouter();
  const locale = useLocale();
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
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editForm, setEditForm] = useState({ title: "", description: "", max_rounds: "5" });
  const [cloning, setCloning] = useState(false);
  const [backgroundRunning, setBackgroundRunning] = useState(false);
  const [showRewriteDialog, setShowRewriteDialog] = useState(false);
  const [rewriteFeedback, setRewriteFeedback] = useState("");
  const [rewriting, setRewriting] = useState(false);
  const [runAfterConnect, setRunAfterConnect] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const pendingTopicRef = useRef("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const agentTitleByKey = (msg: MeetingMessage): string | null => {
    if (msg.role === "user") return null;
    if (msg.agent_id) {
      const a = agents.find((x) => x.id === msg.agent_id);
      return a?.title ?? null;
    }
    if (msg.agent_name) {
      const a = agents.find((x) => x.name === msg.agent_name);
      return a?.title ?? null;
    }
    return null;
  };

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
        setError(getErrorMessage(err, "Failed to load meeting"));
      } finally {
        setLoading(false);
      }
    })();
  }, [meetingId]);

  useEffect(() => {
    if (!teamId) return;
    agentsAPI.listByTeam(teamId).then(setAgents).catch(() => {});
  }, [teamId]);

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
    startRound(1, topic || undefined, locale === "zh" || locale === "en" ? locale : undefined);
    setTopic("");
  };

  const handleRun = () => {
    if (connected) {
      handleRunWS();
    } else {
      pendingTopicRef.current = topic;
      setRunAfterConnect(true);
      connect();
    }
  };

  const handleRunHTTP = async () => {
    try {
      setRunning(true);
      setError(null);
      const data = await meetingsAPI.run(
        meetingId,
        1,
        topic || undefined,
        locale === "zh" || locale === "en" ? locale : undefined
      );
      setMeeting(data);
      setLiveMessages([]);
      setTopic("");
    } catch (err) {
      setError(getErrorMessage(err, "Failed to run meeting"));
    } finally {
      setRunning(false);
    }
  };

  const handleRunBackground = async () => {
    try {
      setError(null);
      const rounds = Math.max(1, (meeting?.max_rounds ?? 5) - (meeting?.current_round ?? 0));
      await meetingsAPI.runBackground(
        meetingId,
        rounds,
        topic || undefined,
        locale === "zh" || locale === "en" ? locale : undefined
      );
      setBackgroundRunning(true);
      setTopic("");
    } catch (err) {
      setError(getErrorMessage(err, "Failed to start background run"));
    }
  };

  const { status: pollStatus } = useMeetingPolling({
    meetingId,
    enabled: backgroundRunning,
    onStatusChange: (s) => {
      setMeeting((prev) =>
        prev ? { ...prev, status: s.status as Meeting["status"], current_round: s.current_round } : prev
      );
    },
    onComplete: async () => {
      setBackgroundRunning(false);
      setRunning(false);
      // Refresh full meeting data
      try {
        const data = await meetingsAPI.get(meetingId);
        setMeeting(data);
        setLiveMessages([]);
      } catch {
        // ignore
      }
    },
  });

  // When background run is in progress, poll full meeting so new messages appear incrementally
  useEffect(() => {
    if (!backgroundRunning || !meetingId) return;
    const intervalMs = 2000;
    const t = setInterval(async () => {
      try {
        const data = await meetingsAPI.get(meetingId);
        setMeeting(data);
      } catch {
        // ignore
      }
    }, intervalMs);
    return () => clearInterval(t);
  }, [backgroundRunning, meetingId]);

  // When WS connects and user asked to run, start round so messages stream
  useEffect(() => {
    if (!connected || !runAfterConnect) return;
    setRunning(true);
    setError(null);
    startRound(1, pendingTopicRef.current || undefined, locale === "zh" || locale === "en" ? locale : undefined);
    setTopic("");
    setRunAfterConnect(false);
  }, [connected, runAfterConnect, startRound, locale]);

  // On initial load, check if meeting is already running in background
  useEffect(() => {
    if (meeting && !backgroundRunning) {
      meetingsAPI.status(meetingId).then((s) => {
        if (s.background_running) {
          setBackgroundRunning(true);
        }
      }).catch(() => {});
    }
  }, [meeting?.id]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userMessage.trim()) return;

    if (connected) {
      sendUserMessage(userMessage);
    } else {
      meetingsAPI.addMessage(meetingId, userMessage).catch((err) =>
        setError(getErrorMessage(err, "Failed to send"))
      );
    }
    setUserMessage("");
  };

  const handleClone = async () => {
    try {
      setCloning(true);
      const cloned = await meetingsAPI.clone(meetingId);
      router.push(`/teams/${teamId}/meetings/${cloned.id}`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to clone"));
    } finally {
      setCloning(false);
    }
  };

  const handleDownloadTranscript = async () => {
    try {
      const blob = await meetingsAPI.transcript(meetingId);
      downloadBlob(blob, `${meeting?.title || "meeting"}.md`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to download transcript"));
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    const rounds = parseInt(editForm.max_rounds) || 5;
    try {
      const updated = await meetingsAPI.update(meetingId, {
        title: editForm.title,
        description: editForm.description || undefined,
        max_rounds: Math.max(1, Math.min(20, rounds)),
      });
      setMeeting((prev) => prev ? { ...prev, ...updated } : prev);
      setShowEditDialog(false);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to update meeting"));
    }
  };

  const handleDelete = async () => {
    if (!confirm(t("deleteConfirm"))) return;
    try {
      await meetingsAPI.delete(meetingId);
      router.push(`/teams/${teamId}`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete meeting"));
    }
  };

  const handleRewrite = async () => {
    if (!rewriteFeedback.trim()) return;
    try {
      setRewriting(true);
      const rewritten = await meetingsAPI.rewrite(meetingId, rewriteFeedback);
      setShowRewriteDialog(false);
      setRewriteFeedback("");
      router.push(`/teams/${teamId}/meetings/${rewritten.id}`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create rewrite"));
    } finally {
      setRewriting(false);
    }
  };

  const openEditDialog = () => {
    if (meeting) {
      setEditForm({
        title: meeting.title,
        description: meeting.description || "",
        max_rounds: String(meeting.max_rounds),
      });
    }
    setShowEditDialog(true);
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
      <div className="shrink-0 space-y-2 mb-4">
        <Link
          href={`/teams/${teamId}`}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("backToTeam")}
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl sm:text-2xl font-bold truncate">{meeting.title}</h1>
          {meeting.meeting_type && meeting.meeting_type !== "team" && (
            <Badge variant="outline" className="capitalize">
              {meeting.meeting_type === "individual" ? <User className="h-3 w-3 mr-1 inline" /> : <GitMerge className="h-3 w-3 mr-1 inline" />}
              {meeting.meeting_type}
            </Badge>
          )}
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
        {meeting.agenda && (
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">{t("agenda")}:</span>
            <span className="text-muted-foreground">{meeting.agenda}</span>
            {meeting.output_type && meeting.output_type !== "code" && (
              <Badge variant="outline" className="text-xs">{meeting.output_type}</Badge>
            )}
          </div>
        )}
        {meeting.meeting_type === "merge" && meeting.source_meeting_ids && meeting.source_meeting_ids.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">Sources:</span>
            {meeting.source_meeting_ids.map((sid, i) => (
              <Link key={sid} href={`/teams/${teamId}/meetings/${sid}`} className="text-primary hover:underline text-xs">
                Source {i + 1}
              </Link>
            ))}
          </div>
        )}
        {meeting.parent_meeting_id && (
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">Rewrite of:</span>
            <Link href={`/teams/${teamId}/meetings/${meeting.parent_meeting_id}`} className="text-primary hover:underline text-xs">
              Original meeting
            </Link>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm text-muted-foreground mr-auto">
            {t("round", { current: meeting.current_round, max: meeting.max_rounds })}
            {meeting.description && <> &mdash; {meeting.description}</>}
          </p>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" onClick={handleClone} disabled={cloning}>
              {cloning ? <Loader2 className="h-4 w-4 animate-spin" /> : <CopyPlus className="h-4 w-4" />}
              <span className="hidden sm:inline ml-1">{t("clone")}</span>
            </Button>
            <Button variant="outline" size="sm" onClick={handleDownloadTranscript}>
              <FileDown className="h-4 w-4" />
              <span className="hidden sm:inline ml-1">{t("downloadTranscript")}</span>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" className="h-8 w-8">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={openEditDialog}>
                  <Pencil className="h-4 w-4 mr-2" />
                  {t("edit")}
                </DropdownMenuItem>
                {isCompleted && (
                  <DropdownMenuItem onClick={() => setShowRewriteDialog(true)}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Rewrite / Improve
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onClick={handleDelete}>
                  <Trash2 className="h-4 w-4 mr-2" />
                  {t("delete")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {error && (
        <div className="shrink-0 p-3 mb-4 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="chat" className="flex-1 flex flex-col min-h-0">
        <TabsList className="shrink-0">
          <TabsTrigger value="chat">
            <MessageSquare className="h-4 w-4 mr-1" />
            {t("tabChat")}
          </TabsTrigger>
          <TabsTrigger value="summary">
            <BarChart3 className="h-4 w-4 mr-1" />
            {t("tabSummary")}
          </TabsTrigger>
          <TabsTrigger value="artifacts">
            <Code className="h-4 w-4 mr-1" />
            {t("tabArtifacts")}
          </TabsTrigger>
        </TabsList>

        {/* Chat Tab */}
        <TabsContent value="chat" className="flex-1 flex flex-col min-h-0">
          <ScrollArea className="flex-1 mb-4">
            <div className="space-y-3 pr-4">
              {allMessages.length === 0 ? (
                <p className="text-muted-foreground text-sm">{t("noMessages")}</p>
              ) : (
                allMessages.map((msg) => {
                  const isFinalSummary =
                    isCompleted &&
                    meeting.agenda &&
                    msg.round_number === meeting.max_rounds &&
                    msg.role === "assistant";
                  const isCritic = msg.agent_name === "Scientific Critic";
                  const agentTitle = msg.role !== "user" ? agentTitleByKey(msg) : null;
                  return (
                    <div
                      key={msg.id}
                      className={`p-4 rounded-lg border ${
                        isFinalSummary
                          ? "bg-primary/5 border-primary/30 ring-1 ring-primary/20"
                          : isCritic
                          ? "bg-amber-50 border-amber-200 dark:bg-amber-950/20 dark:border-amber-800"
                          : msg.role === "user"
                          ? "bg-primary/5 border-primary/20"
                          : "bg-card"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="font-medium text-sm">
                          {msg.role === "user" ? t("you") : msg.agent_name || "Assistant"}
                        </span>
                        {agentTitle && (
                          <>
                            <span className="text-muted-foreground/60">·</span>
                            <span className="text-xs text-muted-foreground font-normal">
                              {agentTitle}
                            </span>
                          </>
                        )}
                        {isFinalSummary && (
                          <Badge variant="default" className="text-xs">
                            {t("finalSummary")}
                          </Badge>
                        )}
                        {msg.round_number > 0 && (
                          <Badge variant="outline" className="text-xs">
                            R{msg.round_number}
                          </Badge>
                        )}
                      </div>
                      {msg.role === "user" ? (
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                          {msg.content}
                        </p>
                      ) : (
                        <MarkdownContent content={msg.content} className="text-sm text-muted-foreground" />
                      )}
                    </div>
                  );
                })
              )}

              {speaking && (
                <div className="p-4 rounded-lg bg-muted border animate-pulse">
                  <span className="text-sm text-muted-foreground">
                    {t("thinking", {
                      agent: (() => {
                        const a = agents.find((x) => x.name === speaking);
                        return a?.title ? `${speaking} · ${a.title}` : speaking;
                      })(),
                    })}
                  </span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* Background progress indicator */}
          {backgroundRunning && pollStatus && (
            <div className="shrink-0 flex items-center gap-2 px-3 py-2 bg-primary/5 border border-primary/20 rounded-lg text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span>
                {t("backgroundRunning")} — {t("round", { current: pollStatus.current_round, max: pollStatus.max_rounds })}
              </span>
            </div>
          )}

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
                  onClick={handleRun}
                  disabled={running || backgroundRunning || runAfterConnect}
                >
                  <Play className="h-4 w-4 mr-1" />
                  {runAfterConnect
                    ? t("connecting")
                    : running
                    ? t("running")
                    : connected
                    ? t("runLive")
                    : t("run")}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleRunBackground}
                  disabled={running || backgroundRunning}
                  title={t("backgroundRunTitle")}
                >
                  <PlayCircle className="h-4 w-4 mr-1" />
                  <span className="hidden sm:inline">{t("backgroundRun")}</span>
                </Button>
              </div>
            </div>
          )}
        </TabsContent>

        {/* Summary Tab */}
        <TabsContent value="summary" className="flex-1 overflow-auto">
          <MeetingSummaryPanel meetingId={meetingId} />
        </TabsContent>

        {/* Artifacts Tab */}
        <TabsContent value="artifacts" className="flex-1 overflow-auto">
          <ArtifactsPanel meetingId={meetingId} meetingTitle={meeting.title} />
        </TabsContent>
      </Tabs>

      {/* Rewrite Dialog */}
      <Dialog open={showRewriteDialog} onOpenChange={setShowRewriteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rewrite / Improve Meeting</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <p className="text-sm text-muted-foreground">
              Provide feedback on what to improve. A new meeting will be created with the original output and your feedback injected as context.
            </p>
            <Textarea
              value={rewriteFeedback}
              onChange={(e) => setRewriteFeedback(e.target.value)}
              placeholder="What should be improved? Be specific..."
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRewriteDialog(false)}>
              {tc("cancel")}
            </Button>
            <Button onClick={handleRewrite} disabled={rewriting || !rewriteFeedback.trim()}>
              {rewriting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              Create Rewrite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("edit")}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4">
            <Input
              value={editForm.title}
              onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
              placeholder={t("title")}
              required
            />
            <Textarea
              value={editForm.description}
              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
              placeholder={t("descriptionPlaceholder")}
              rows={3}
            />
            <Input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              placeholder="5"
              value={editForm.max_rounds}
              onChange={(e) => {
                const v = e.target.value.replace(/[^0-9]/g, "");
                setEditForm({ ...editForm, max_rounds: v });
              }}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowEditDialog(false)}>
                {tc("cancel")}
              </Button>
              <Button type="submit">{tc("save")}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
