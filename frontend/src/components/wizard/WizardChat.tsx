"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Send, Loader2, FlaskConical, User, CheckCircle2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Link } from "@/i18n/navigation";
import { onboardingAPI } from "@/lib/api";
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

export function WizardChat() {
  const t = useTranslations("wizard");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [createdTeamId, setCreatedTeamId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Internal state for multi-stage flow
  const [stage, setStage] = useState<OnboardingStage>("problem");
  const [history, setHistory] = useState<OnboardingChatMessage[]>([]);
  const [context, setContext] = useState<Record<string, unknown>>({});
  const [teamSuggestion, setTeamSuggestion] = useState<TeamSuggestion | null>(null);
  const [mirrorConfig, setMirrorConfig] = useState<MirrorConfig | null>(null);

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
        stage,
        message: msg,
        conversation_history: newHistory,
        context,
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

      // Build the assistant message
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: response.message,
        proposedTeam: teamSuggestion?.agents || (response.data?.team_suggestion as TeamSuggestion)?.agents,
        isComplete: response.next_stage === null,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Advance stage
      if (response.next_stage) {
        setStage(response.next_stage);
      }

      // If complete, generate the team
      if (response.next_stage === null || response.stage === "complete") {
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
          } catch {
            // Team generation failed, but wizard is still complete
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
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <ScrollArea className="flex-1 px-1" ref={scrollRef}>
        <div className="mx-auto max-w-2xl space-y-4 py-4">
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

          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}

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

      {/* Input area */}
      <div className="border-t border-border/50 px-4 py-3">
        <div className="mx-auto max-w-2xl">
          {isComplete ? (
            <div className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 p-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                <div>
                  <p className="text-sm font-medium">{t("teamReady")}</p>
                  <p className="text-xs text-muted-foreground">
                    {t("teamReadyDesc")}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleReset}>
                  {t("startOver")}
                </Button>
                <Button size="sm" asChild>
                  <Link href={createdTeamId ? `/teams/${createdTeamId}` : "/teams"}>
                    <Users className="mr-1.5 h-3.5 w-3.5" />
                    {t("viewTeam")}
                  </Link>
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
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
                className="min-h-[44px] max-h-[120px] resize-none text-sm"
                rows={1}
                disabled={isLoading}
              />
              <Button
                size="icon"
                className="h-[44px] w-[44px] shrink-0"
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
          )}

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
  );
}

/** Single message bubble */
function MessageBubble({ message }: { message: ChatMessage }) {
  const t = useTranslations("wizard");
  const isUser = message.role === "user";

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
        className={`max-w-[80%] space-y-3 ${
          isUser ? "text-right" : "text-left"
        }`}
      >
        <div
          className={`inline-block rounded-lg px-3 py-2 text-sm leading-relaxed ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted/50 text-foreground"
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {/* Team proposal cards */}
        {message.proposedTeam && message.proposedTeam.length > 0 && (
          <div className="space-y-2 text-left">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              {t("proposedTeam")}
            </p>
            {message.proposedTeam.map((agent, i) => (
              <div
                key={i}
                className="rounded-lg border border-border/50 bg-background p-3"
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted-foreground">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="text-sm font-medium">{agent.name}</span>
                  <Badge variant="secondary" className="text-[10px]">
                    {agent.title}
                  </Badge>
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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
