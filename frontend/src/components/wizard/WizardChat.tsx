"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Send, Loader2, FlaskConical, User, CheckCircle2, Users, ChevronUp, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/i18n/navigation";
import { onboardingAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import { MarkdownContent } from "@/components/MarkdownContent";
import { useMobileGesture } from "@/contexts/MobileGestureContext";
import { useSwipeGesture } from "@/hooks/useSwipeGesture";
import { EditAgentDialog } from "@/components/EditAgentDialog";
import type {
  OnboardingStage,
  OnboardingChatMessage,
  OnboardingChatResponse,
  AgentSuggestion,
  TeamSuggestion,
  MirrorConfig,
} from "@/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  proposedTeam?: AgentSuggestion[];
  isComplete?: boolean;
}

const WIZARD_STORAGE_KEY = "vlab_wizard_state";

interface WizardState {
  messages: ChatMessage[];
  stage: OnboardingStage;
  history: OnboardingChatMessage[];
  context: Record<string, unknown>;
  teamSuggestion: TeamSuggestion | null;
  mirrorConfig: MirrorConfig | null;
  isComplete: boolean;
  createdTeamId: string | null;
}

function loadWizardState(): Partial<WizardState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = sessionStorage.getItem(WIZARD_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // Corrupted data - ignore
  }
  return {};
}

function saveWizardState(state: WizardState) {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(WIZARD_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage full - ignore
  }
}

export function WizardChat() {
  const t = useTranslations("wizard");
  const locale = useLocale();
  const saved = useRef(loadWizardState());
  const { isMobile, inputVisible, setInputVisible } = useMobileGesture();

  const inputSwipeDown = useSwipeGesture({
    onSwipeDown: useCallback(() => setInputVisible(false), [setInputVisible]),
  });
  const showBarSwipeUp = useSwipeGesture({
    onSwipeUp: useCallback(() => setInputVisible(true), [setInputVisible]),
  });

  const [messages, setMessages] = useState<ChatMessage[]>(saved.current.messages || []);
  const [input, setInput] = useState("");
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(saved.current.isComplete || false);
  const [createdTeamId, setCreatedTeamId] = useState<string | null>(saved.current.createdTeamId || null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Internal state for multi-stage flow
  const [stage, setStage] = useState<OnboardingStage>(saved.current.stage || "problem");
  const [history, setHistory] = useState<OnboardingChatMessage[]>(saved.current.history || []);
  const [context, setContext] = useState<Record<string, unknown>>(saved.current.context || {});
  const [teamSuggestion, setTeamSuggestion] = useState<TeamSuggestion | null>(saved.current.teamSuggestion || null);
  const [mirrorConfig, setMirrorConfig] = useState<MirrorConfig | null>(saved.current.mirrorConfig || null);

  // Persist state to sessionStorage on every change
  const persistState = useCallback(() => {
    saveWizardState({ messages, stage, history, context, teamSuggestion, mirrorConfig, isComplete, createdTeamId });
  }, [messages, stage, history, context, teamSuggestion, mirrorConfig, isComplete, createdTeamId]);

  useEffect(() => {
    persistState();
  }, [persistState]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  async function handleSend() {
    const msg = input.trim();
    if (!msg || isLoading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setIsLoading(true);

    const newHistory: OnboardingChatMessage[] = [
      ...history,
      { role: "user", content: msg },
    ];

    try {
      const response: OnboardingChatResponse = await onboardingAPI.chat({
        message: msg,
        conversation_history: newHistory,
        context,
        locale: locale === "zh" || locale === "en" ? locale : undefined,
      });

      // Update history
      const updatedHistory: OnboardingChatMessage[] = [
        ...newHistory,
        { role: "assistant", content: response.message },
      ];
      setHistory(updatedHistory);

      // Update context with response data
      const newContext = { ...context };
      if (response.data) {
        if (response.data.response_lang !== undefined) {
          newContext.response_lang = response.data.response_lang;
        }
        if (stage === "problem" && response.data.analysis) {
          newContext.analysis = response.data.analysis;
        }
        if (response.data.team_suggestion) {
          const ts = response.data.team_suggestion as TeamSuggestion;
          newContext.team_suggestion = ts;
          setTeamSuggestion(ts);
        }
        if (response.data.mirror_config) {
          const mc = response.data.mirror_config as MirrorConfig;
          newContext.mirror_config = mc;
          setMirrorConfig(mc);
        }
      }
      setContext(newContext);

      // Build the assistant message — only attach agent cards when this response returns a new team_suggestion (show cards once)
      const newTeamFromResponse = (response.data?.team_suggestion as TeamSuggestion)?.agents;
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.message,
        proposedTeam: newTeamFromResponse ?? undefined,
        isComplete: response.next_stage === null,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Update stage from backend (semantic: backend infers from context)
      setStage(response.next_stage ?? response.stage);

      // If complete, generate the team automatically
      if (
        response.next_stage === null ||
        response.next_stage === "complete" ||
        response.stage === "complete"
      ) {
        const ts = (newContext.team_suggestion as TeamSuggestion) || teamSuggestion;
        const mc = (newContext.mirror_config as MirrorConfig) || mirrorConfig;
        if (ts) {
          try {
            const team = await onboardingAPI.generateTeam({
              team_name: ts.team_name,
              team_description: ts.team_description,
              agents: ts.agents,
              mirror_config: mc || undefined,
            });
            setCreatedTeamId(team.id);
          } catch (err) {
            // Show error to user instead of silently failing
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: `Failed to create team: ${getErrorMessage(err, "Unknown error")}. You can try again from the Teams page.`,
              },
            ]);
          }
        }
        setIsComplete(true);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? `Error: ${error.message}`
              : t("errorGeneric"),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleEditAgent(agentIndex: number, updatedAgent: AgentSuggestion) {
    const lastProposalIndex = messages.reduce(
      (last, m, idx) => (m.proposedTeam ? idx : last),
      -1
    );
    if (lastProposalIndex < 0 || !teamSuggestion) return;
    setTeamSuggestion((prev) =>
      prev
        ? {
            ...prev,
            agents: prev.agents.map((a, j) =>
              j === agentIndex ? updatedAgent : a
            ),
          }
        : null
    );
    setMessages((prev) =>
      prev.map((m, i) =>
        i === lastProposalIndex && m.proposedTeam
          ? {
              ...m,
              proposedTeam: m.proposedTeam.map((a, j) =>
                j === agentIndex ? updatedAgent : a
              ),
            }
          : m
      )
    );
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleReset() {
    setMessages([]);
    setInput("");
    setStage("problem");
    setHistory([]);
    setContext({});
    setTeamSuggestion(null);
    setMirrorConfig(null);
    setIsComplete(false);
    setCreatedTeamId(null);
    sessionStorage.removeItem(WIZARD_STORAGE_KEY);
  }

  const inputContent = isComplete ? (
    <div className="rounded-lg border border-border/50 bg-muted/30 p-4 space-y-3">
      <div className="flex items-center gap-3">
        <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
        <div>
          <p className="text-sm font-medium">{t("teamReady")}</p>
          <p className="text-xs text-muted-foreground">
            {t("teamReadyDesc")}
          </p>
        </div>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" className="flex-1 sm:flex-none" onClick={handleReset}>
          {t("startOver")}
        </Button>
        <Button size="sm" className="flex-1 sm:flex-none" asChild>
          <Link href={createdTeamId ? `/teams/${createdTeamId}` : "/teams"}>
            <Users className="mr-1.5 h-3.5 w-3.5" />
            {t("viewTeam")}
          </Link>
        </Button>
      </div>
    </div>
  ) : (
    <div className="flex gap-2">
      <div className="relative flex-1 min-w-0">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsInputFocused(true)}
          onBlur={() => setIsInputFocused(false)}
          placeholder=""
          aria-label={
            stage === "problem"
              ? t("placeholder")
              : stage === "clarification"
                ? t("placeholderClarify")
                : stage === "team_suggestion"
                  ? t("placeholderReview")
                  : stage === "mirror_config"
                    ? t("placeholderMirror")
                    : t("placeholder")
          }
          className="min-h-[52px] max-h-[120px] resize-none text-sm py-2.5"
          rows={1}
          disabled={isLoading}
        />
        {/* Custom placeholder: 2-line max, vertically centered, ellipsis when overflow */}
        {!input.trim() && !isInputFocused && (
          <div
            className="absolute inset-0 flex items-center px-3 py-2.5 pointer-events-none rounded-md border border-transparent"
            aria-hidden
          >
            <span className="text-sm text-muted-foreground line-clamp-2 overflow-hidden text-ellipsis break-words">
              {stage === "problem"
                ? t("placeholder")
                : stage === "clarification"
                  ? t("placeholderClarify")
                  : stage === "team_suggestion"
                    ? t("placeholderReview")
                    : stage === "mirror_config"
                      ? t("placeholderMirror")
                      : t("placeholder")}
            </span>
          </div>
        )}
      </div>
      <Button
        size="icon"
        className="h-[52px] w-[52px] shrink-0 self-end"
        onClick={handleSend}
        disabled={!input.trim() || isLoading}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
      </Button>
    </div>
  );

  const showInputBar = isMobile && !isComplete && !inputVisible;

  return (
    <div className="flex h-full flex-col min-h-0">
      {/* Messages area */}
      <ScrollArea className="flex-1 min-h-0 px-1" ref={scrollRef}>
        <div className="mx-auto max-w-2xl space-y-4 py-4 px-2 sm:px-0">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full border border-border/50">
                <FlaskConical className="h-5 w-5 text-muted-foreground" />
              </div>
              <h2 className="text-lg font-semibold tracking-tight">
                {t("title")}
              </h2>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">
                {t("subtitle")}
              </p>
            </div>
          )}

          {(() => {
            const lastProposalIndex = messages.reduce(
              (last, m, idx) => (m.proposedTeam ? idx : last),
              -1
            );
            return messages.map((msg, i) => (
              <MessageBubble
                key={i}
                message={msg}
                messageIndex={i}
                isEditable={i === lastProposalIndex && !!msg.proposedTeam?.length}
                onEditAgent={handleEditAgent}
                teamSuggestion={teamSuggestion}
              />
            ));
          })()}

          {isLoading && (
            <div className="flex items-start gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border/50 bg-background">
                <FlaskConical className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-2">
                <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">
                  {t("thinking")}
                </span>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input area - sticky at bottom, height animates so messages + input = viewport */}
      <div className="shrink-0 border-t border-border/50 bg-background overflow-hidden pb-[env(safe-area-inset-bottom)]">
        {/* Swipe-up bar when input hidden (mobile only) */}
        {showInputBar && (
          <div
            className="flex items-center justify-center py-3 px-4 cursor-pointer touch-manipulation active:bg-muted/50 transition-colors duration-200"
            onClick={() => setInputVisible(true)}
            {...showBarSwipeUp}
          >
            <ChevronUp className="h-4 w-4 text-muted-foreground mr-1" />
            <span className="text-xs text-muted-foreground">{t("showInput")}</span>
          </div>
        )}

        {/* Main input panel - collapses when hidden so messages area expands */}
        <div
          className={`overflow-hidden transition-[max-height,opacity] duration-300 ease-out ${
            isMobile && !isComplete && !inputVisible
              ? "max-h-0 opacity-0 pointer-events-none"
              : "max-h-[220px] opacity-100"
          }`}
          {...(isMobile && !isComplete && inputVisible ? inputSwipeDown : {})}
        >
          <div className="px-4 py-3">
            <div className="mx-auto max-w-2xl">
              {inputContent}

              {!isComplete && messages.length === 0 && (
                <div className="mt-2 text-center">
                  <Link
                    href="/teams"
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {t("skipToManual")} &rarr;
                  </Link>
                </div>
              )}

              {!isComplete && messages.length > 0 && (
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    {t(`stage.${stage}`)}
                  </span>
                  <button
                    onClick={handleReset}
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {t("startOver")}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface MessageBubbleProps {
  message: ChatMessage;
  messageIndex: number;
  isEditable: boolean;
  onEditAgent: (agentIndex: number, updated: AgentSuggestion) => void;
  teamSuggestion: TeamSuggestion | null;
}

/** Single message bubble; agent cards in the latest proposal are editable. */
function MessageBubble({
  message,
  messageIndex,
  isEditable,
  onEditAgent,
  teamSuggestion,
}: MessageBubbleProps) {
  const t = useTranslations("wizard");
  const isUser = message.role === "user";
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<AgentSuggestion | null>(null);

  const openEdit = (agent: AgentSuggestion, index: number) => {
    setEditForm({ ...agent });
    setEditingIndex(index);
  };
  const closeEdit = () => {
    setEditingIndex(null);
    setEditForm(null);
  };
  const handleSaveEdit = (data: { name: string; title: string; expertise: string; goal: string; role: string; model: string }) => {
    if (editingIndex !== null) {
      onEditAgent(editingIndex, data);
      closeEdit();
    }
  };

  return (
    <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border/50 ${
          isUser ? "bg-primary text-primary-foreground" : "bg-background"
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5" />
        ) : (
          <FlaskConical className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </div>

      {/* Content */}
      <div
        className={`min-w-0 max-w-[85%] space-y-3 ${
          isUser ? "text-right" : "text-left"
        }`}
      >
        {isUser ? (
          <div className="inline-block rounded-lg px-3 py-2 text-sm leading-relaxed bg-primary text-primary-foreground whitespace-pre-wrap">
            {message.content}
          </div>
        ) : (
          <div className="text-sm leading-relaxed">
            <MarkdownContent content={message.content} />
          </div>
        )}

        {/* Team proposal cards */}
        {message.proposedTeam && message.proposedTeam.length > 0 && (
          <div className="space-y-2 text-left">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {t("proposedTeam")}
            </p>
            {message.proposedTeam.map((agent, i) => (
              <div
                key={i}
                className={`rounded-lg border border-border/50 bg-background p-3 ${
                  isEditable ? "cursor-pointer hover:border-border transition-colors" : ""
                }`}
                onClick={() => isEditable && openEdit(agent, i)}
                role={isEditable ? "button" : undefined}
                aria-label={isEditable ? t("editAgent") : undefined}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-mono text-xs text-muted-foreground shrink-0">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="text-sm font-medium">{agent.name}</span>
                    <Badge variant="secondary" className="text-[10px] shrink-0">
                      {agent.title}
                    </Badge>
                  </div>
                  {isEditable && (
                    <Pencil className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  )}
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {agent.goal}
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  <Badge variant="outline" className="text-[10px] font-normal">
                    {agent.expertise}
                  </Badge>
                  <Badge variant="outline" className="text-[10px] font-normal">
                    {agent.model}
                  </Badge>
                </div>
                {agent.model_reason && (
                  <p className="mt-1 text-[10px] text-muted-foreground/70 italic">
                    {agent.model_reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit agent — same dialog as team page */}
      <EditAgentDialog
        open={editingIndex !== null}
        onOpenChange={(open) => !open && closeEdit()}
        agent={editForm}
        variant="suggestion"
        onSave={handleSaveEdit}
      />
    </div>
  );
}
