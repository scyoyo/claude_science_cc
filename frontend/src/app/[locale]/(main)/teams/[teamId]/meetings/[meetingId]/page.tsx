"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI, agendaAPI, agentsAPI, artifactsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { useMeetingPolling } from "@/hooks/useMeetingPolling";
import { downloadBlob } from "@/lib/utils";
import { useMeetingWebSocket, type WSMessage } from "@/hooks/useMeetingWebSocket";
import { useMeetingSSE, type SSEMessage } from "@/hooks/useMeetingSSE";
import type { Meeting, MeetingWithMessages, MeetingMessage, Agent, RoundPlan, CodeArtifact } from "@/types";
import { getMeetingPhase, getPhaseLabel } from "@/lib/meetingPhase";
import MeetingSummaryPanel from "@/components/MeetingSummaryPanel";
import ArtifactsPanel from "@/components/ArtifactsPanel";
import ArtifactViewer from "@/components/ArtifactViewer";
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
  FileCode,
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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedRound, setSelectedRound] = useState(0); // 0 = show all
  const [chatArtifacts, setChatArtifacts] = useState<CodeArtifact[]>([]);
  const [viewerArtifact, setViewerArtifact] = useState<CodeArtifact | null>(null);
  const [viewerOpen, setViewerOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  /** Pending run to start only after SSE is connected, so we don't miss real-time events. */
  const pendingRunRef = useRef<{ rounds: number; topic?: string; locale?: string } | null>(null);

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

  const { connected: wsConnected, speaking, connect, disconnect, sendUserMessage, startRound } =
    useMeetingWebSocket({
      meetingId,
      onMessage: onWSMessage,
      onError: onWSError,
      onRoundComplete,
      onMeetingComplete,
    });

  // SSE real-time streaming (works through HTTP proxy, unlike WS on Railway)
  const onSSEMessage = useCallback((msg: SSEMessage) => {
    const newMsg: MeetingMessage = {
      id: msg.id || `sse-${Date.now()}-${Math.random()}`,
      meeting_id: meetingId,
      agent_id: msg.agent_id || null,
      role: msg.role || "assistant",
      agent_name: msg.agent_name || null,
      content: msg.content || "",
      round_number: msg.round_number || 0,
      created_at: new Date().toISOString(),
    };
    setLiveMessages((prev) => [...prev, newMsg]);
    setTimeout(scrollToBottom, 50);
  }, [meetingId, scrollToBottom]);

  const onSSERoundComplete = useCallback((round: number, totalRounds: number) => {
    setMeeting((prev) =>
      prev ? { ...prev, current_round: round, status: round >= totalRounds ? "completed" : "pending" } : prev
    );
  }, []);

  const onSSEComplete = useCallback(async () => {
    setBackgroundRunning(false);
    setRunning(false);
    try {
      const data = await meetingsAPI.get(meetingId);
      setMeeting(data);
      setLiveMessages([]);
      artifactsAPI.listByMeeting(meetingId).then(setChatArtifacts).catch(() => {});
    } catch {
      // ignore
    }
  }, [meetingId]);

  const onSSEError = useCallback((detail: string) => {
    setError(detail);
    setBackgroundRunning(false);
    setRunning(false);
  }, []);

  const { connected: sseConnected } = useMeetingSSE({
    meetingId,
    enabled: backgroundRunning,
    onMessage: onSSEMessage,
    onRoundComplete: onSSERoundComplete,
    onComplete: onSSEComplete,
    onError: onSSEError,
  });

  const connected = wsConnected || sseConnected;

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
    artifactsAPI.listByMeeting(meetingId).then(setChatArtifacts).catch(() => setChatArtifacts([]));
  }, [meetingId]);

  useEffect(() => {
    if (meeting && meeting.status !== "completed") {
      connect();
    }
    return () => disconnect();
  }, [meeting?.id, meeting?.status]);

  /** Run N rounds: connect SSE first, then start run when connected so messages stream in real time. */
  const handleRunBackground = (rounds: number) => {
    setError(null);
    const localeParam = locale === "zh" || locale === "en" ? locale : undefined;
    pendingRunRef.current = { rounds, topic: topic || undefined, locale: localeParam };
    setTopic("");
    setBackgroundRunning(true);  // SSE connects; once connected we fire run-background in effect below
  };

  // Start run after SSE is connected so messages stream in real time; fallback after 8s if SSE never connects
  useEffect(() => {
    if (!backgroundRunning || !pendingRunRef.current) return;
    const pending = pendingRunRef.current;

    if (sseConnected) {
      pendingRunRef.current = null;
      meetingsAPI
        .runBackground(meetingId, pending.rounds, pending.topic, pending.locale)
        .catch((err) => {
          setError(getErrorMessage(err, "Failed to start run"));
          setBackgroundRunning(false);
        });
      return;
    }

    const fallback = setTimeout(() => {
      if (!pendingRunRef.current) return;
      pendingRunRef.current = null;
      meetingsAPI
        .runBackground(meetingId, pending.rounds, pending.topic, pending.locale)
        .catch((err) => {
          setError(getErrorMessage(err, "Failed to start run"));
          setBackgroundRunning(false);
        });
    }, 8000);
    return () => clearTimeout(fallback);
  }, [backgroundRunning, sseConnected, meetingId]);

  /** "Run 1 round" button */
  const handleRun = () => handleRunBackground(1);

  /** "Run all remaining" button */
  const handleRunAll = () => {
    const remaining = Math.max(1, (meeting?.max_rounds ?? 5) - (meeting?.current_round ?? 0));
    handleRunBackground(remaining);
  };

  const { status: pollStatus } = useMeetingPolling({
    meetingId,
    enabled: backgroundRunning && !sseConnected,
    onStatusChange: (s) => {
      setMeeting((prev) =>
        prev ? { ...prev, status: s.status as Meeting["status"], current_round: s.current_round } : prev
      );
    },
    onComplete: async () => {
      setBackgroundRunning(false);
      setRunning(false);
      // Refresh full meeting data and artifacts (auto-extract may have run)
      try {
        const data = await meetingsAPI.get(meetingId);
        setMeeting(data);
        setLiveMessages([]);
        artifactsAPI.listByMeeting(meetingId).then(setChatArtifacts).catch(() => {});
      } catch {
        // ignore
      }
    },
  });

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
  const filteredMessages = selectedRound === 0
    ? allMessages
    : allMessages.filter((msg) => msg.round_number === selectedRound);

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "secondary" as const;
      case "running": return "default" as const;
      case "failed": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  return (
    <div className="flex flex-col min-h-0 h-[calc(100dvh-theme(spacing.16))] sm:h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="shrink-0 space-y-2 mb-3 sm:mb-4">
        <button
          type="button"
          onClick={() => router.back()}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          title={t("backToTeam")}
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {tc("back")}
        </button>
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
        <TabsList className="shrink-0 flex w-full overflow-x-auto min-h-11 p-1">
          <TabsTrigger value="chat" className="flex-1 sm:flex-initial min-h-11 px-2 sm:px-3 text-xs sm:text-sm">
            <MessageSquare className="h-4 w-4 mr-1 shrink-0" />
            {t("tabChat")}
          </TabsTrigger>
          <TabsTrigger value="summary" className="flex-1 sm:flex-initial min-h-11 px-2 sm:px-3 text-xs sm:text-sm">
            <BarChart3 className="h-4 w-4 mr-1 shrink-0" />
            {t("tabSummary")}
          </TabsTrigger>
          <TabsTrigger value="artifacts" className="flex-1 sm:flex-initial min-h-11 px-2 sm:px-3 text-xs sm:text-sm">
            <Code className="h-4 w-4 mr-1 shrink-0" />
            {t("tabArtifacts")}
          </TabsTrigger>
        </TabsList>

        {/* Chat Tab */}
        <TabsContent value="chat" className="flex-1 flex flex-col min-h-0">
          {/* Round Selector */}
          {meeting.max_rounds > 1 && (
            <div className="shrink-0 flex items-center gap-1 mb-3 overflow-x-auto pb-1 -mx-1 px-1 min-h-10">
              <Button
                variant={selectedRound === 0 ? "default" : "outline"}
                size="sm"
                className="shrink-0 h-8 min-w-[2.5rem] px-2.5 text-xs touch-manipulation"
                onClick={() => setSelectedRound(0)}
              >
                {t("roundAll")}
              </Button>
              {Array.from({ length: meeting.max_rounds }, (_, i) => i + 1).map((r) => {
                const plan = (meeting.round_plans as RoundPlan[] | undefined)?.find((p) => p.round === r);
                const phase = getMeetingPhase(r, meeting.max_rounds);
                const hasMessages = allMessages.some((m) => m.round_number === r);
                return (
                  <Button
                    key={r}
                    variant={selectedRound === r ? "default" : "outline"}
                    size="sm"
                    className="shrink-0 h-8 min-w-[2.5rem] px-2.5 text-xs relative touch-manipulation"
                    onClick={() => setSelectedRound(r)}
                    title={plan?.title || getPhaseLabel(phase, t)}
                  >
                    R{r}
                    {hasMessages && selectedRound !== r && (
                      <span className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 rounded-full bg-primary" />
                    )}
                  </Button>
                );
              })}
            </div>
          )}

          {/* Round Header (when specific round selected) */}
          {selectedRound > 0 && (() => {
            const plan = (meeting.round_plans as RoundPlan[] | undefined)?.find((p) => p.round === selectedRound);
            const phase = getMeetingPhase(selectedRound, meeting.max_rounds);
            const phaseLabel = getPhaseLabel(phase, t);
            return (
              <div className="shrink-0 mb-3 p-3 bg-muted/50 rounded-lg border text-sm space-y-1">
                <div className="font-medium">
                  {t("round", { current: selectedRound, max: meeting.max_rounds })}
                  {" · "}{phaseLabel}
                  {plan?.title && <> — {plan.title}</>}
                </div>
                {plan?.goal && (
                  <div className="text-muted-foreground">
                    <span className="font-medium">{t("roundGoal")}:</span> {plan.goal}
                  </div>
                )}
                {plan?.expected_output && (
                  <div className="text-muted-foreground">
                    <span className="font-medium">{t("roundExpectedOutput")}:</span> {plan.expected_output}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Generated files in this meeting — open in same-page viewer */}
          {chatArtifacts.length > 0 && (
            <div className="shrink-0 mb-3 p-3 rounded-lg border bg-muted/30">
              <p className="text-xs font-medium text-muted-foreground mb-2">{t("generatedFiles")}</p>
              <div className="flex flex-wrap gap-2">
                {chatArtifacts.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => {
                      setViewerArtifact(a);
                      setViewerOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-sm bg-background border hover:bg-accent hover:text-accent-foreground transition-colors"
                  >
                    <FileCode className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate max-w-[180px] sm:max-w-[240px]">{a.filename}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <ScrollArea className="flex-1 mb-3 sm:mb-4">
            <div className="space-y-3 pr-2 sm:pr-4">
              {filteredMessages.length === 0 ? (
                <p className="text-muted-foreground text-sm">{t("noMessages")}</p>
              ) : (
                filteredMessages.map((msg, idx) => {
                  const isFinalSummary =
                    isCompleted &&
                    meeting.agenda &&
                    msg.round_number === meeting.max_rounds &&
                    msg.role === "assistant";
                  const isCritic = msg.agent_name === "Scientific Critic";
                  const agentTitle = msg.role !== "user" ? agentTitleByKey(msg) : null;

                  // Round divider in "All" mode
                  const showDivider = selectedRound === 0 &&
                    msg.round_number > 0 &&
                    (idx === 0 || filteredMessages[idx - 1].round_number !== msg.round_number);

                  const roundPlan = showDivider
                    ? (meeting.round_plans as RoundPlan[] | undefined)?.find((p) => p.round === msg.round_number)
                    : null;
                  const dividerPhase = showDivider
                    ? getPhaseLabel(getMeetingPhase(msg.round_number, meeting.max_rounds), t)
                    : "";
                  const dividerGoal = roundPlan?.goal || "";

                  return (
                    <div key={msg.id}>
                      {showDivider && (
                        <div className="flex items-center gap-2 my-2 text-xs text-muted-foreground">
                          <div className="flex-1 border-t" />
                          <span className="shrink-0 font-medium">
                            R{msg.round_number} · {dividerPhase}
                            {dividerGoal && `: ${dividerGoal}`}
                          </span>
                          <div className="flex-1 border-t" />
                        </div>
                      )}
                      <div
                        className={`p-3 sm:p-4 rounded-lg border break-words ${
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
                          {msg.round_number > 0 && selectedRound === 0 && (
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
            <div className="shrink-0 space-y-3 border-t pt-3 sm:pt-4 pb-4">
              <form onSubmit={handleSendMessage} className="flex gap-2">
                <Input
                  value={userMessage}
                  onChange={(e) => setUserMessage(e.target.value)}
                  placeholder={t("sendMessage")}
                  className="flex-1 min-h-10"
                />
                <Button type="submit" size="icon" className="shrink-0 min-h-10 min-w-10">
                  <Send className="h-4 w-4" />
                </Button>
              </form>

              <div className="flex flex-col sm:flex-row gap-2">
                <Input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder={t("topic")}
                  className="flex-1 min-h-10"
                />
                <div className="flex gap-2">
                  <Button
                    onClick={handleRun}
                    disabled={running || backgroundRunning}
                    className="flex-1 sm:flex-initial min-h-10"
                  >
                    <Play className="h-4 w-4 mr-1 shrink-0" />
                    {backgroundRunning ? t("running") : t("run")}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleRunAll}
                    disabled={running || backgroundRunning}
                    title={t("backgroundRunTitle")}
                    className="min-h-10 px-3"
                  >
                    <PlayCircle className="h-4 w-4 sm:mr-1 shrink-0" />
                    <span className="hidden sm:inline">{t("backgroundRun")}</span>
                  </Button>
                </div>
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

      {/* Artifact viewer (same-page modal) */}
      <ArtifactViewer
        artifact={viewerArtifact}
        open={viewerOpen}
        onOpenChange={(open) => {
          setViewerOpen(open);
          if (!open) setViewerArtifact(null);
        }}
      />

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
