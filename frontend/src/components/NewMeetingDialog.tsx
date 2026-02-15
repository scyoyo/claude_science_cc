"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { meetingsAPI, agendaAPI, agentsAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { Meeting, Team, MeetingCreate, RoundPlan } from "@/types";
import { getMeetingPhase, getPhaseLabel } from "@/lib/meetingPhase";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2, Loader2, Sparkles } from "lucide-react";

export interface NewMeetingDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When provided (team page), use this team and meetings. */
  teamId?: string;
  /** When provided (meetings page), show team selector and load meetings/agents on select. */
  teams?: Team[];
  /** Meetings for context selector (team page). */
  meetings?: Meeting[];
  /** Pre-selected participant ids (team page "start with selected"). */
  initialParticipantIds?: string[] | null;
  /** Pre-filled title (e.g. "Meeting with A, B"). */
  initialTitle?: string;
  /** After create: navigate to meeting (team page). Omit to stay on page (meetings page). */
  navigateToMeeting?: boolean;
  /** Called after meeting is created. */
  onSuccess?: (meeting: Meeting) => void;
}

const defaultForm = {
  title: "",
  description: "",
  agenda: "",
  output_type: "code" as string,
  agenda_questions: [] as string[],
  context_meeting_ids: [] as string[],
  max_rounds: "5",
};

export function NewMeetingDialog({
  open,
  onOpenChange,
  teamId: propTeamId,
  teams = [],
  meetings: propMeetings = [],
  initialParticipantIds = null,
  initialTitle = "",
  navigateToMeeting = false,
  onSuccess,
}: NewMeetingDialogProps) {
  const t = useTranslations("teamDetail");
  const tm = useTranslations("meeting");
  const tc = useTranslations("common");
  const router = useRouter();

  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [loadedMeetings, setLoadedMeetings] = useState<Meeting[]>([]);
  const [loadedAgents, setLoadedAgents] = useState<{ id: string; name: string; title: string; is_mirror: boolean }[]>([]);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [form, setForm] = useState(defaultForm);
  const [roundPlans, setRoundPlans] = useState<RoundPlan[]>([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [generatingAgenda, setGeneratingAgenda] = useState(false);
  const [creatingMeeting, setCreatingMeeting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isTeamContext = !!propTeamId;
  const effectiveTeamId = propTeamId ?? selectedTeamId;
  const meetings = isTeamContext ? propMeetings : loadedMeetings;
  const agents = loadedAgents;
  const effectiveParticipantIds = isTeamContext
    ? (initialParticipantIds ?? [])
    : participantIds;

  // Reset form when opening; apply initial title/participants when from team context
  useEffect(() => {
    if (open) {
      setForm((f) => ({
        ...defaultForm,
        title: initialTitle || f.title || defaultForm.title,
      }));
      setNewQuestion("");
      setRoundPlans([]);
      setError(null);
      if (isTeamContext) {
        setSelectedTeamId("");
        setLoadedMeetings([]);
        setLoadedAgents([]);
        setParticipantIds(initialParticipantIds ?? []);
      } else {
        setSelectedTeamId("");
        setLoadedMeetings([]);
        setLoadedAgents([]);
        setParticipantIds([]);
      }
    }
  }, [open, isTeamContext, initialTitle, initialParticipantIds]);

  // Load meetings and agents when team is selected (meetings page)
  useEffect(() => {
    if (!open || !selectedTeamId || isTeamContext) return;
    Promise.all([
      meetingsAPI.listByTeam(selectedTeamId),
      agentsAPI.listByTeam(selectedTeamId),
    ])
      .then(([meetingsList, agentsList]) => {
        setLoadedMeetings(meetingsList);
        setLoadedAgents(agentsList);
      })
      .catch(() => {
        setLoadedMeetings([]);
        setLoadedAgents([]);
      });
  }, [open, selectedTeamId, isTeamContext]);

  const handleGenerateAgenda = async () => {
    if (!effectiveTeamId) return;
    try {
      setGeneratingAgenda(true);
      setError(null);
      const result = await agendaAPI.autoGenerate({
        team_id: effectiveTeamId,
        participant_agent_ids: effectiveParticipantIds.length > 0 ? effectiveParticipantIds : undefined,
      });
      setForm((f) => ({
        ...f,
        agenda: result.agenda,
        agenda_questions: result.questions,
        max_rounds: String(result.suggested_rounds),
        // Auto-fill title if user hasn't typed one yet
        title: f.title.trim() ? f.title : (result.title || f.title),
      }));
      setRoundPlans(result.round_plans || []);
    } catch (e) {
      setError(getErrorMessage(e, "Failed to generate agenda"));
    } finally {
      setGeneratingAgenda(false);
    }
  };

  const addQuestion = () => {
    const q = newQuestion.trim();
    if (q) {
      setForm((f) => ({ ...f, agenda_questions: [...f.agenda_questions, q] }));
      setNewQuestion("");
    }
  };

  const removeQuestion = (i: number) => {
    setForm((f) => ({
      ...f,
      agenda_questions: f.agenda_questions.filter((_, idx) => idx !== i),
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectiveTeamId || !form.title.trim()) return;
    setCreatingMeeting(true);
    setError(null);
    try {
      const payload: MeetingCreate = {
        team_id: effectiveTeamId,
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        agenda: form.agenda.trim() || undefined,
        agenda_questions: form.agenda_questions.length > 0 ? form.agenda_questions : undefined,
        output_type: form.output_type,
        context_meeting_ids: form.context_meeting_ids.length > 0 ? form.context_meeting_ids : undefined,
        participant_agent_ids: effectiveParticipantIds.length > 0 ? effectiveParticipantIds : undefined,
        max_rounds: Math.max(1, Math.min(20, parseInt(form.max_rounds, 10) || 5)),
        round_plans: roundPlans.length > 0 ? roundPlans : undefined,
      };
      const created = await meetingsAPI.create(payload);
      onSuccess?.(created);
      onOpenChange(false);
      if (navigateToMeeting) {
        router.push(`/teams/${effectiveTeamId}/meetings/${created.id}`);
      }
    } catch (e) {
      setError(getErrorMessage(e, "Failed to create meeting"));
    } finally {
      setCreatingMeeting(false);
    }
  };

  const showForm = isTeamContext || (!!selectedTeamId && selectedTeamId.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] p-4 sm:p-6 overflow-hidden gap-4" showCloseButton style={{ display: "flex", flexDirection: "column" }}>
        <DialogHeader className="shrink-0">
          <DialogTitle>{t("addMeeting")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 gap-4 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden pr-1 -mr-1 space-y-4">
          {/* Team selector (meetings page only) */}
          {!isTeamContext && teams.length > 0 && (
            <div className="space-y-2">
              <Label>{t("selectTeam")}</Label>
              <Select
                value={selectedTeamId}
                onValueChange={setSelectedTeamId}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t("selectTeam")} />
                </SelectTrigger>
                <SelectContent>
                  {teams.map((team) => (
                    <SelectItem key={team.id} value={team.id}>
                      {team.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Participant checkboxes (meetings page when agents loaded) */}
          {!isTeamContext && agents.length > 0 && (
            <div className="space-y-2">
              <Label>{t("agents")}</Label>
              <div className="space-y-1 max-h-28 overflow-y-auto">
                {agents.filter((a) => !a.is_mirror).map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={participantIds.includes(a.id)}
                      onChange={(e) => {
                        if (e.target.checked) setParticipantIds((prev) => [...prev, a.id]);
                        else setParticipantIds((prev) => prev.filter((id) => id !== a.id));
                      }}
                      className="rounded"
                    />
                    <span className="truncate">{a.name} ({a.title})</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {showForm && (
            <>
              <div className="space-y-2">
                <Label>{t("meetingTitle")}</Label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder={t("meetingTitle")}
                  required
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label>{t("meetingAgenda")}</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleGenerateAgenda}
                    disabled={generatingAgenda}
                  >
                    {generatingAgenda ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Sparkles className="h-3.5 w-3.5 mr-1" />}
                    {t("generateAgenda")}
                  </Button>
                </div>
                <Textarea
                  value={form.agenda}
                  onChange={(e) => setForm((f) => ({ ...f, agenda: e.target.value }))}
                  placeholder={t("meetingAgendaPlaceholder")}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("meetingOutputType")}</Label>
                <Select
                  value={form.output_type}
                  onValueChange={(v) => setForm((f) => ({ ...f, output_type: v as "code" }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="code">{t("meetingOutputCode")}</SelectItem>
                    <SelectItem value="report">{t("meetingOutputReport")}</SelectItem>
                    <SelectItem value="paper">{t("meetingOutputPaper")}</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {form.output_type === "code" && t("meetingOutputCodeHint")}
                  {form.output_type === "report" && t("meetingOutputReportHint")}
                  {form.output_type === "paper" && t("meetingOutputPaperHint")}
                </p>
              </div>
              <div className="space-y-2">
                <Label>{t("meetingAgendaQuestions")}</Label>
                {form.agenda_questions.map((q, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-sm flex-1 bg-muted px-2 py-1 rounded">{q}</span>
                    <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeQuestion(i)}>
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                ))}
                <div className="flex gap-2">
                  <Input
                    value={newQuestion}
                    onChange={(e) => setNewQuestion(e.target.value)}
                    placeholder={t("meetingAgendaQuestionsPlaceholder")}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addQuestion(); } }}
                  />
                  <Button type="button" variant="outline" size="sm" onClick={addQuestion}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">{t("meetingAgendaQuestionsHint")}</p>
              </div>
              {meetings.filter((m) => m.status === "completed").length > 0 && (
                <div className="space-y-2">
                  <Label>{t("contextMeetings")}</Label>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {meetings
                      .filter((m) => m.status === "completed")
                      .map((m) => (
                        <label key={m.id} className="flex items-center gap-2 text-sm cursor-pointer">
                          <input
                            type="checkbox"
                            checked={form.context_meeting_ids.includes(m.id)}
                            onChange={(e) => {
                              const ids = e.target.checked
                                ? [...form.context_meeting_ids, m.id]
                                : form.context_meeting_ids.filter((id) => id !== m.id);
                              setForm((f) => ({ ...f, context_meeting_ids: ids }));
                            }}
                            className="rounded"
                          />
                          <span className="truncate">{m.title}</span>
                        </label>
                      ))}
                  </div>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>{t("meetingMaxRounds")}</Label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    placeholder="5"
                    value={form.max_rounds}
                    onChange={(e) => {
                      const v = e.target.value.replace(/[^0-9]/g, "");
                      setForm((f) => ({ ...f, max_rounds: v }));
                    }}
                  />
                  <p className="text-xs text-muted-foreground">{t("meetingMaxRoundsHint")}</p>
                </div>
                <div className="space-y-2">
                  <Label>{t("meetingDescription")}</Label>
                  <Input
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder={t("meetingDescription")}
                  />
                </div>
              </div>

              {/* Round Plans Preview */}
              {roundPlans.length > 0 && (
                <div className="space-y-2">
                  <Label>{tm("roundPlans")} ({roundPlans.length})</Label>
                  <div className="border rounded-lg divide-y text-sm">
                    {roundPlans.map((rp) => {
                      const maxRounds = parseInt(form.max_rounds, 10) || roundPlans.length;
                      const phase = getMeetingPhase(rp.round, maxRounds);
                      const phaseLabel = getPhaseLabel(phase, tm);
                      return (
                        <div key={rp.round} className="px-3 py-2 space-y-0.5">
                          <div className="font-medium">
                            R{rp.round} · {phaseLabel}
                            {rp.title && <span className="font-normal text-muted-foreground"> — {rp.title}</span>}
                          </div>
                          {rp.goal && (
                            <div className="text-muted-foreground text-xs">
                              <span className="font-medium">{tm("roundGoal")}:</span> {rp.goal}
                            </div>
                          )}
                          {rp.expected_output && (
                            <div className="text-muted-foreground text-xs">
                              <span className="font-medium">{tm("roundExpectedOutput")}:</span> {rp.expected_output}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter className="shrink-0 pt-2 border-t border-border/50">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={creatingMeeting}>
              {tc("cancel")}
            </Button>
            <Button
              type="submit"
              disabled={creatingMeeting || !showForm || !form.title.trim() || (!isTeamContext && !selectedTeamId)}
            >
              {creatingMeeting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              {tc("create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
