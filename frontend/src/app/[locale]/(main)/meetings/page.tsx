"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { meetingsAPI, teamsAPI, agentsAPI, agendaAPI } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";
import type { Meeting, Team, Agent, MeetingType, AgendaStrategy } from "@/types";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MessageSquare, Search, Trash2, Plus, Loader2, ArrowLeftRight, Sparkles, Users, User, GitMerge } from "lucide-react";

type StatusFilter = "all" | "pending" | "completed" | "failed";

export default function MeetingsPage() {
  const t = useTranslations("meetings");
  const tc = useTranslations("common");
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [creatingMeeting, setCreatingMeeting] = useState(false);
  const [teamAgents, setTeamAgents] = useState<Agent[]>([]);
  const [meetingForm, setMeetingForm] = useState({
    team_id: "",
    title: "",
    description: "",
    max_rounds: 5,
    agenda: "",
    output_type: "code",
    agenda_questions: [] as string[],
    context_meeting_ids: [] as string[],
    meeting_type: "team" as MeetingType,
    individual_agent_id: "",
    source_meeting_ids: [] as string[],
    agenda_strategy: "manual" as AgendaStrategy,
    participant_agent_ids: [] as string[],
  });
  const [newQuestion, setNewQuestion] = useState("");
  const [generatingAgenda, setGeneratingAgenda] = useState(false);

  const loadMeetings = async () => {
    try {
      setLoading(true);
      const [meetingsData, teamsData] = await Promise.all([
        meetingsAPI.list(),
        teamsAPI.list(),
      ]);
      setMeetings(meetingsData);
      setTeams(teamsData);
      setError(null);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load meetings"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMeetings();
  }, []);

  const handleCreateMeeting = async () => {
    if (!meetingForm.team_id || !meetingForm.title.trim()) return;
    try {
      setCreatingMeeting(true);
      await meetingsAPI.create({
        team_id: meetingForm.team_id,
        title: meetingForm.title,
        description: meetingForm.description || undefined,
        agenda: meetingForm.agenda.trim() || undefined,
        agenda_questions: meetingForm.agenda_questions.length > 0 ? meetingForm.agenda_questions : undefined,
        output_type: meetingForm.output_type,
        context_meeting_ids: meetingForm.context_meeting_ids.length > 0 ? meetingForm.context_meeting_ids : undefined,
        meeting_type: meetingForm.meeting_type,
        individual_agent_id: meetingForm.meeting_type === "individual" ? meetingForm.individual_agent_id || undefined : undefined,
        source_meeting_ids: meetingForm.meeting_type === "merge" ? meetingForm.source_meeting_ids : undefined,
        participant_agent_ids: meetingForm.participant_agent_ids.length > 0 ? meetingForm.participant_agent_ids : undefined,
        agenda_strategy: meetingForm.agenda_strategy,
        max_rounds: meetingForm.max_rounds,
      });
      setShowCreate(false);
      setMeetingForm({ team_id: "", title: "", description: "", max_rounds: 5, agenda: "", output_type: "code", agenda_questions: [], context_meeting_ids: [], meeting_type: "team", individual_agent_id: "", source_meeting_ids: [], agenda_strategy: "manual", participant_agent_ids: [] });
      setNewQuestion("");
      await loadMeetings();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create meeting"));
    } finally {
      setCreatingMeeting(false);
    }
  };

  // Load agents when team changes
  useEffect(() => {
    if (meetingForm.team_id) {
      agentsAPI.listByTeam(meetingForm.team_id).then(setTeamAgents).catch(() => setTeamAgents([]));
    } else {
      setTeamAgents([]);
    }
  }, [meetingForm.team_id]);

  const handleAutoGenerate = async (participantIds?: string[]) => {
    if (!meetingForm.team_id) return;
    const ids = participantIds ?? meetingForm.participant_agent_ids;
    try {
      setGeneratingAgenda(true);
      const result = await agendaAPI.autoGenerate({
        team_id: meetingForm.team_id,
        goal: meetingForm.description || meetingForm.title,
        prev_meeting_ids: meetingForm.context_meeting_ids,
        participant_agent_ids: ids.length > 0 ? ids : undefined,
      });
      setMeetingForm((f) => ({
        ...f,
        agenda: result.agenda,
        agenda_questions: result.questions,
        max_rounds: result.suggested_rounds,
        agenda_strategy: "ai_auto",
      }));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to generate agenda"));
    } finally {
      setGeneratingAgenda(false);
    }
  };

  const addQuestion = () => {
    const q = newQuestion.trim();
    if (q) {
      setMeetingForm((f) => ({ ...f, agenda_questions: [...f.agenda_questions, q] }));
      setNewQuestion("");
    }
  };

  const removeQuestion = (index: number) => {
    setMeetingForm((f) => ({
      ...f,
      agenda_questions: f.agenda_questions.filter((_, i) => i !== index),
    }));
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t("deleteConfirm"))) return;
    try {
      await meetingsAPI.delete(id);
      setMeetings((prev) => prev.filter((m) => m.id !== id));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete meeting"));
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <div className="flex flex-col sm:flex-row gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/meetings/compare">
              <ArrowLeftRight className="h-4 w-4 mr-1" />
              {t("compareMeetings")}
            </Link>
          </Button>
          <Dialog open={showCreate} onOpenChange={setShowCreate}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-1" />
                {t("create")}
              </Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("newMeeting")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label>{t("selectTeam")}</Label>
                <Select
                  value={meetingForm.team_id}
                  onValueChange={(v) => setMeetingForm((f) => ({ ...f, team_id: v }))}
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
              {/* Meeting Type */}
              <div className="space-y-2">
                <Label>Meeting Type</Label>
                <div className="flex gap-2">
                  {([
                    { key: "team" as const, icon: Users, label: "Team" },
                    { key: "individual" as const, icon: User, label: "Individual" },
                    { key: "merge" as const, icon: GitMerge, label: "Merge" },
                  ]).map(({ key, icon: Icon, label }) => (
                    <Button
                      key={key}
                      type="button"
                      size="sm"
                      variant={meetingForm.meeting_type === key ? "default" : "outline"}
                      onClick={() => setMeetingForm((f) => ({ ...f, meeting_type: key }))}
                    >
                      <Icon className="h-4 w-4 mr-1" />
                      {label}
                    </Button>
                  ))}
                </div>
              </div>
              {/* Individual: agent picker */}
              {meetingForm.meeting_type === "individual" && teamAgents.length > 0 && (
                <div className="space-y-2">
                  <Label>Select Agent</Label>
                  <Select
                    value={meetingForm.individual_agent_id}
                    onValueChange={(v) => setMeetingForm((f) => ({ ...f, individual_agent_id: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose agent for 1:1 with critic" />
                    </SelectTrigger>
                    <SelectContent>
                      {teamAgents.map((a) => (
                        <SelectItem key={a.id} value={a.id}>{a.name} ({a.title})</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              {/* Merge: source meetings */}
              {meetingForm.meeting_type === "merge" && meetings.filter((m) => m.status === "completed").length > 0 && (
                <div className="space-y-2">
                  <Label>Source Meetings (completed)</Label>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {meetings.filter((m) => m.status === "completed").map((m) => (
                      <label key={m.id} className="flex items-center gap-2 text-sm cursor-pointer">
                        <input
                          type="checkbox"
                          checked={meetingForm.source_meeting_ids.includes(m.id)}
                          onChange={(e) => {
                            const ids = e.target.checked
                              ? [...meetingForm.source_meeting_ids, m.id]
                              : meetingForm.source_meeting_ids.filter((id) => id !== m.id);
                            setMeetingForm((f) => ({ ...f, source_meeting_ids: ids }));
                          }}
                          className="rounded"
                        />
                        <span className="truncate">{m.title}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
              {/* Participant agents selector (team & individual types) */}
              {meetingForm.team_id && teamAgents.length > 0 && meetingForm.meeting_type !== "merge" && (
                <div className="space-y-2">
                  <Label>{t("selectParticipants") || "Participants"}</Label>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {teamAgents.filter((a) => !a.is_mirror).map((a) => (
                      <label key={a.id} className="flex items-center gap-2 text-sm cursor-pointer">
                        <input
                          type="checkbox"
                          checked={meetingForm.participant_agent_ids.includes(a.id)}
                          onChange={(e) => {
                            const ids = e.target.checked
                              ? [...meetingForm.participant_agent_ids, a.id]
                              : meetingForm.participant_agent_ids.filter((id) => id !== a.id);
                            setMeetingForm((f) => ({ ...f, participant_agent_ids: ids }));
                            // Auto-generate agenda when agents are selected
                            if (e.target.checked && ids.length > 0) {
                              handleAutoGenerate(ids);
                            }
                          }}
                          className="rounded"
                        />
                        <span className="truncate">{a.name} ({a.title})</span>
                      </label>
                    ))}
                  </div>
                  {generatingAgenda && (
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Generating agenda...
                    </div>
                  )}
                </div>
              )}
              <div className="space-y-2">
                <Label>{t("meetingTitle")}</Label>
                <Input
                  value={meetingForm.title}
                  onChange={(e) => setMeetingForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder={t("meetingTitle")}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("meetingAgenda")}</Label>
                <Textarea
                  value={meetingForm.agenda}
                  onChange={(e) => setMeetingForm((f) => ({ ...f, agenda: e.target.value }))}
                  placeholder={t("meetingAgendaPlaceholder")}
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("meetingOutputType")}</Label>
                <Select
                  value={meetingForm.output_type}
                  onValueChange={(v) => setMeetingForm((f) => ({ ...f, output_type: v }))}
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
              </div>
              {/* Agenda Strategy */}
              <div className="space-y-2">
                <Label>Agenda Strategy</Label>
                <div className="flex items-center gap-2">
                  <Select
                    value={meetingForm.agenda_strategy}
                    onValueChange={(v) => setMeetingForm((f) => ({ ...f, agenda_strategy: v as AgendaStrategy }))}
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="manual">Manual</SelectItem>
                      <SelectItem value="ai_auto">AI Auto-Generate</SelectItem>
                      <SelectItem value="agent_voting">Agent Voting</SelectItem>
                      <SelectItem value="chain">Chain (from previous)</SelectItem>
                    </SelectContent>
                  </Select>
                  {meetingForm.agenda_strategy === "ai_auto" && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handleAutoGenerate()}
                      disabled={generatingAgenda || !meetingForm.team_id}
                    >
                      {generatingAgenda ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                      <span className="ml-1">Generate</span>
                    </Button>
                  )}
                </div>
              </div>
              <div className="space-y-2">
                <Label>{t("meetingAgendaQuestions")}</Label>
                {meetingForm.agenda_questions.map((q, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-sm flex-1 bg-muted px-2 py-1 rounded">{q}</span>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeQuestion(i)}>
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
                  <Button variant="outline" size="sm" onClick={addQuestion}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              {/* Context meetings selector */}
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
                            checked={meetingForm.context_meeting_ids.includes(m.id)}
                            onChange={(e) => {
                              const ids = e.target.checked
                                ? [...meetingForm.context_meeting_ids, m.id]
                                : meetingForm.context_meeting_ids.filter((id) => id !== m.id);
                              setMeetingForm((f) => ({ ...f, context_meeting_ids: ids }));
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
                    type="number"
                    min={1}
                    max={20}
                    value={meetingForm.max_rounds}
                    onChange={(e) => setMeetingForm((f) => ({ ...f, max_rounds: Number(e.target.value) }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t("meetingDescription")}</Label>
                  <Input
                    value={meetingForm.description}
                    onChange={(e) => setMeetingForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder={t("meetingDescription")}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreate(false)}>
                {tc("cancel")}
              </Button>
              <Button
                onClick={handleCreateMeeting}
                disabled={creatingMeeting || !meetingForm.team_id || !meetingForm.title.trim()}
              >
                {creatingMeeting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                {tc("create")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        </div>
      </div>

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
        <div className="flex flex-wrap gap-2">
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
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <CardTitle className="text-base flex items-center gap-2">
                      <MessageSquare className="h-4 w-4 shrink-0" />
                      {meeting.title}
                    </CardTitle>
                    <div className="flex flex-wrap items-center gap-2">
                      {meeting.meeting_type && meeting.meeting_type !== "team" && (
                        <Badge variant="outline" className="text-xs capitalize">
                          {meeting.meeting_type === "individual" ? <User className="h-3 w-3 mr-1" /> : <GitMerge className="h-3 w-3 mr-1" />}
                          {meeting.meeting_type}
                        </Badge>
                      )}
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
