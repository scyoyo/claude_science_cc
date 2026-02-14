"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { teamsAPI, agentsAPI, meetingsAPI, agendaAPI } from "@/lib/api";
import { getErrorMessage, downloadBlob } from "@/lib/utils";
import type { TeamWithAgents, Meeting, TeamStats, AgentMetrics } from "@/types";
import TemplatesBrowser from "@/components/TemplatesBrowser";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardAction } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ArrowLeft, Plus, Trash2, Pencil, Workflow, MessageSquare, Bot, Loader2, LayoutTemplate, CheckSquare, Download, PlayCircle, CopyPlus } from "lucide-react";
import { SHOW_VISUAL_EDITOR, SHOW_EXPORT_TEAM } from "@/lib/feature-flags";
import type { Agent } from "@/types";
import { MODEL_OPTIONS } from "@/lib/models";
import { EditAgentDialog, type EditAgentFormData } from "@/components/EditAgentDialog";

export default function TeamDetailPage() {
  const params = useParams();
  const router = useRouter();
  const teamId = params.teamId as string;
  const t = useTranslations("teamDetail");
  const tc = useTranslations("common");

  const [team, setTeam] = useState<TeamWithAgents | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [showNewMeeting, setShowNewMeeting] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);

  const [agentForm, setAgentForm] = useState({
    name: "",
    title: "",
    expertise: "",
    goal: "",
    role: "",
    model: "gpt-4",
  });
  const [meetingForm, setMeetingForm] = useState({
    title: "", description: "", max_rounds: "5",
    agenda: "", output_type: "code", agenda_questions: [] as string[],
    context_meeting_ids: [] as string[],
  });
  const [newQuestion, setNewQuestion] = useState("");
  const [creatingMeeting, setCreatingMeeting] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [teamStats, setTeamStats] = useState<TeamStats | null>(null);
  const [agentMetricsMap, setAgentMetricsMap] = useState<Record<string, AgentMetrics>>({});

  // Select mode state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  /** When set, new meeting will be created with only these agents as participants. */
  const [participantIdsForNewMeeting, setParticipantIdsForNewMeeting] = useState<string[] | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      const [teamData, meetingsData, statsData] = await Promise.all([
        teamsAPI.get(teamId),
        meetingsAPI.listByTeam(teamId),
        teamsAPI.stats(teamId).catch(() => null),
      ]);
      setTeam(teamData);
      setMeetings(meetingsData);
      if (statsData) setTeamStats(statsData);
      setError(null);

      // Load agent metrics in background
      if (teamData.agents.length > 0) {
        const metricsEntries = await Promise.all(
          teamData.agents.map((a) =>
            agentsAPI.metrics(a.id).then((m) => [a.id, m] as const).catch(() => null)
          )
        );
        const map: Record<string, AgentMetrics> = {};
        for (const entry of metricsEntries) {
          if (entry) map[entry[0]] = entry[1];
        }
        setAgentMetricsMap(map);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load team"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [teamId]);

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await agentsAPI.create({ ...agentForm, team_id: teamId });
      setAgentForm({ name: "", title: "", expertise: "", goal: "", role: "", model: "gpt-4" });
      setShowAddAgent(false);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create agent"));
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(t("deleteAgent"))) return;
    try {
      await agentsAPI.delete(agentId);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete agent"));
    }
  };

  const handleCloneAgent = async (agentId: string) => {
    try {
      await agentsAPI.clone(agentId);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to clone agent"));
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(t("batchDeleteConfirm", { count: selectedIds.size }))) return;
    try {
      await agentsAPI.batchDelete([...selectedIds]);
      setSelectedIds(new Set());
      setSelectMode(false);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to delete agents"));
    }
  };

  const [addingMirrors, setAddingMirrors] = useState(false);
  const handleAddMirrorForSelected = async () => {
    if (!team) return;
    const primaryIds = team.agents
      .filter((a) => selectedIds.has(a.id) && !a.is_mirror)
      .map((a) => a.id);
    if (primaryIds.length === 0) return;
    try {
      setAddingMirrors(true);
      await agentsAPI.createMirrors(primaryIds);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to add mirror agents"));
    } finally {
      setAddingMirrors(false);
    }
  };

  const handleExportTeam = async () => {
    try {
      const blob = await teamsAPI.exportTeam(teamId);
      downloadBlob(blob, `${team?.name || "team"}.json`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to export team"));
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!team) return;
    setSelectedIds(new Set(team.agents.map((a) => a.id)));
  };

  const deselectAll = () => setSelectedIds(new Set());

  const openEditAgent = (agent: Agent) => {
    if (selectMode) {
      toggleSelect(agent.id);
      return;
    }
    setEditingAgent(agent);
  };

  const handleEditAgentSave = async (data: EditAgentFormData) => {
    if (!editingAgent) return;
    try {
      await agentsAPI.update(editingAgent.id, data as Record<string, unknown>);
      setEditingAgent(null);
      await loadData();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to update agent"));
    }
  };

  const handleCreateMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = meetingForm.title.trim();
    const description = meetingForm.description.trim();
    if (!title) return;
    const rounds = parseInt(meetingForm.max_rounds) || 5;
    setCreatingMeeting(true);
    try {
      const created = await meetingsAPI.create({
        team_id: teamId,
        title,
        description: description || undefined,
        agenda: meetingForm.agenda.trim() || undefined,
        agenda_questions: meetingForm.agenda_questions.length > 0 ? meetingForm.agenda_questions : undefined,
        output_type: meetingForm.output_type,
        context_meeting_ids: meetingForm.context_meeting_ids.length > 0 ? meetingForm.context_meeting_ids : undefined,
        participant_agent_ids: participantIdsForNewMeeting && participantIdsForNewMeeting.length > 0 ? participantIdsForNewMeeting : undefined,
        max_rounds: Math.max(1, Math.min(20, rounds)),
      });
      setMeetingForm({ title: "", description: "", max_rounds: "5", agenda: "", output_type: "code", agenda_questions: [], context_meeting_ids: [] });
      setNewQuestion("");
      setShowNewMeeting(false);
      setParticipantIdsForNewMeeting(null);
      setSelectedIds(new Set());
      setSelectMode(false);
      await loadData();
      router.push(`/teams/${teamId}/meetings/${created.id}`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create meeting"));
    } finally {
      setCreatingMeeting(false);
    }
  };

  const [generatingAgenda, setGeneratingAgenda] = useState(false);

  const openNewMeetingWithSelectedAgents = async () => {
    if (selectedIds.size === 0) return;
    const ids = [...selectedIds];
    setParticipantIdsForNewMeeting(ids);
    const names = ids
      .map((id) => team?.agents.find((a) => a.id === id)?.name)
      .filter(Boolean) as string[];
    setMeetingForm((f) => ({
      ...f,
      title: names.length > 0 ? `${t("meetingWith")} ${names.join(", ")}` : f.title,
    }));
    setShowNewMeeting(true);
    // Auto-generate agenda for selected agents
    try {
      setGeneratingAgenda(true);
      const result = await agendaAPI.autoGenerate({
        team_id: teamId,
        participant_agent_ids: ids,
      });
      setMeetingForm((f) => ({
        ...f,
        agenda: result.agenda,
        agenda_questions: result.questions,
        max_rounds: String(result.suggested_rounds),
      }));
    } catch {
      // Graceful fallback: no API key or error - user can fill manually
    } finally {
      setGeneratingAgenda(false);
    }
  };

  const addQuestion = () => {
    const q = newQuestion.trim();
    if (q) {
      setMeetingForm({ ...meetingForm, agenda_questions: [...meetingForm.agenda_questions, q] });
      setNewQuestion("");
    }
  };

  const removeQuestion = (index: number) => {
    setMeetingForm({
      ...meetingForm,
      agenda_questions: meetingForm.agenda_questions.filter((_, i) => i !== index),
    });
  };

  if (loading) return <p className="text-muted-foreground">{tc("loading")}</p>;
  if (!team) return <p className="text-destructive">Team not found</p>;

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "secondary" as const;
      case "running": return "default" as const;
      case "failed": return "destructive" as const;
      default: return "outline" as const;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link href="/teams" className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" />
          {t("backToTeams")}
        </Link>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-3">
          <h1 className="text-2xl font-bold">{team.name}</h1>
          {(SHOW_VISUAL_EDITOR || SHOW_EXPORT_TEAM) && (
            <div className="flex flex-col sm:flex-row gap-2">
              {SHOW_VISUAL_EDITOR && (
                <Button asChild size="sm" variant="outline">
                  <Link href={`/teams/${teamId}/editor`}>
                    <Workflow className="h-4 w-4 mr-1" />
                    {t("visualEditor")}
                  </Link>
                </Button>
              )}
              {SHOW_EXPORT_TEAM && (
                <Button size="sm" variant="outline" onClick={handleExportTeam}>
                  <Download className="h-4 w-4 mr-1" />
                  {t("exportTeam")}
                </Button>
              )}
            </div>
          )}
        </div>
        {team.description && (
          <p className="mt-1 text-muted-foreground">{team.description}</p>
        )}
      </div>

      {/* Stats Bar */}
      {teamStats && (
        <div className="flex gap-4 flex-wrap text-sm">
          {[
            { label: t("stats.agents"), value: teamStats.agent_count },
            { label: t("stats.meetings"), value: teamStats.meeting_count },
            { label: t("stats.completed"), value: teamStats.completed_meetings },
            { label: t("stats.messages"), value: teamStats.message_count },
            { label: t("stats.artifacts"), value: teamStats.artifact_count },
          ].map((s) => (
            <div key={s.label} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-muted">
              <span className="font-medium">{s.value}</span>
              <span className="text-muted-foreground">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Agents Section */}
      <section>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {t("agents")} ({team.agents.length})
          </h2>
          <div className="flex flex-col sm:flex-row gap-2">
            {team.agents.length > 0 && (
              <Button
                size="sm"
                variant={selectMode ? "default" : "outline"}
                onClick={() => { setSelectMode(!selectMode); setSelectedIds(new Set()); }}
              >
                <CheckSquare className="h-4 w-4 mr-1" />
                {t("selectAgents")}
              </Button>
            )}
            <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                  <LayoutTemplate className="h-4 w-4 mr-1" />
                  {t("fromTemplate")}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>{t("browseTemplates")}</DialogTitle>
                </DialogHeader>
                <TemplatesBrowser
                  teamId={teamId}
                  onApplied={() => { setShowTemplates(false); loadData(); }}
                />
              </DialogContent>
            </Dialog>
            <Dialog open={showAddAgent} onOpenChange={setShowAddAgent}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="h-4 w-4 mr-1" />
                  {t("addAgent")}
                </Button>
              </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>{t("createAgent")}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreateAgent} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    value={agentForm.name}
                    onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })}
                    placeholder={t("agentName")}
                    required
                  />
                  <Input
                    value={agentForm.title}
                    onChange={(e) => setAgentForm({ ...agentForm, title: e.target.value })}
                    placeholder={t("agentTitle")}
                    required
                  />
                </div>
                <Input
                  value={agentForm.expertise}
                  onChange={(e) => setAgentForm({ ...agentForm, expertise: e.target.value })}
                  placeholder={t("expertise")}
                  required
                />
                <Input
                  value={agentForm.goal}
                  onChange={(e) => setAgentForm({ ...agentForm, goal: e.target.value })}
                  placeholder={t("goal")}
                  required
                />
                <Input
                  value={agentForm.role}
                  onChange={(e) => setAgentForm({ ...agentForm, role: e.target.value })}
                  placeholder={t("role")}
                  required
                />
                <Select
                  value={agentForm.model}
                  onValueChange={(v) => setAgentForm({ ...agentForm, model: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MODEL_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setShowAddAgent(false)}>
                    {tc("cancel")}
                  </Button>
                  <Button type="submit">{t("createAgent")}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          </div>
        </div>

        {/* Batch action bar — wraps on mobile to avoid overflow */}
        {selectMode && team.agents.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-4 p-2 rounded-md bg-muted min-w-0 max-w-full">
            <Button size="sm" variant="outline" onClick={selectedIds.size === team.agents.length ? deselectAll : selectAll} className="shrink-0">
              {selectedIds.size === team.agents.length ? t("deselectAll") : t("selectAll")}
            </Button>
            {selectedIds.size > 0 && (
              <>
                <Button size="sm" variant="default" onClick={openNewMeetingWithSelectedAgents} className="shrink-0">
                  <PlayCircle className="h-4 w-4 mr-1 shrink-0" />
                  <span className="whitespace-nowrap">{t("startMeetingWithSelected", { count: selectedIds.size })}</span>
                </Button>
                <Button size="sm" variant="destructive" onClick={handleBatchDelete} className="shrink-0">
                  <Trash2 className="h-4 w-4 mr-1 shrink-0" />
                  <span className="whitespace-nowrap">{t("batchDelete", { count: selectedIds.size })}</span>
                </Button>
                {team.agents.some((a) => selectedIds.has(a.id) && !a.is_mirror) && (
                  <Button size="sm" variant="outline" onClick={handleAddMirrorForSelected} disabled={addingMirrors} className="shrink-0 border-border bg-background hover:bg-muted">
                    {addingMirrors ? <Loader2 className="h-4 w-4 animate-spin mr-1 shrink-0" /> : <CopyPlus className="h-4 w-4 mr-1 shrink-0" />}
                    <span className="whitespace-nowrap">{t("addMirrorAgentSelected", { count: team.agents.filter((a) => selectedIds.has(a.id) && !a.is_mirror).length })}</span>
                  </Button>
                )}
              </>
            )}
          </div>
        )}

        {team.agents.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("noAgents")}</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {team.agents.map((agent) => (
              <Card
                key={agent.id}
                className={`cursor-pointer hover:border-primary/50 transition-colors overflow-hidden ${selectMode && selectedIds.has(agent.id) ? "border-primary ring-1 ring-primary" : ""}`}
                onClick={() => openEditAgent(agent)}
              >
                <CardHeader>
                  <div className="flex items-start gap-2 min-w-0">
                    {selectMode && (
                      <input
                        type="checkbox"
                        checked={selectedIds.has(agent.id)}
                        onChange={() => toggleSelect(agent.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="mt-0.5 rounded"
                      />
                    )}
                    <Bot className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <CardTitle className="text-base flex items-center gap-2 overflow-hidden">
                        <span className="truncate">{agent.name}</span>
                        {agent.is_mirror && (
                          <Badge variant="secondary" className="shrink-0">{t("mirror")}</Badge>
                        )}
                      </CardTitle>
                      <CardDescription className="truncate">{agent.title}</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1 text-sm text-muted-foreground">
                    <p className="line-clamp-2"><span className="font-medium text-foreground">{t("expertise")}:</span> {agent.expertise}</p>
                    <p className="line-clamp-2"><span className="font-medium text-foreground">{t("goal")}:</span> {agent.goal}</p>
                  </div>
                  <div className="mt-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px] font-normal max-w-[100px] truncate rounded-full px-2">
                        {agent.model}
                      </Badge>
                      {agentMetricsMap[agent.id] && (
                        <span className="text-[10px] text-muted-foreground">
                          {t("agentMetrics.messages", { count: agentMetricsMap[agent.id].total_messages })}
                          {" · "}
                          {t("agentMetrics.meetings", { count: agentMetricsMap[agent.id].total_meetings })}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => { e.stopPropagation(); handleCloneAgent(agent.id); }}
                        title={t("cloneAgent")}
                      >
                        <CopyPlus className="h-3.5 w-3.5" />
                      </Button>
                      <span className="text-muted-foreground/60 p-1" aria-hidden>
                        <Pencil className="h-3.5 w-3.5" />
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => { e.stopPropagation(); handleDeleteAgent(agent.id); }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Meetings Section */}
      <section>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {t("meetings")} ({meetings.length})
          </h2>
          <Dialog
            open={showNewMeeting}
            onOpenChange={(open) => {
              setShowNewMeeting(open);
              if (!open) setParticipantIdsForNewMeeting(null);
            }}
          >
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4 mr-1" />
                {t("addMeeting")}
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>{t("addMeeting")}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreateMeeting} className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("meetingTitle")}</Label>
                  <Input
                    value={meetingForm.title}
                    onChange={(e) => setMeetingForm({ ...meetingForm, title: e.target.value })}
                    placeholder={t("meetingTitle")}
                    autoFocus
                    required
                  />
                </div>
                {generatingAgenda && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {t("generatingAgenda") || "Generating agenda..."}
                  </div>
                )}
                <div className="space-y-2">
                  <Label>{t("meetingAgenda")}</Label>
                  <Textarea
                    value={meetingForm.agenda}
                    onChange={(e) => setMeetingForm({ ...meetingForm, agenda: e.target.value })}
                    placeholder={t("meetingAgendaPlaceholder")}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t("meetingOutputType")}</Label>
                  <Select
                    value={meetingForm.output_type}
                    onValueChange={(v) => setMeetingForm({ ...meetingForm, output_type: v })}
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
                <div className="space-y-2">
                  <Label>{t("meetingAgendaQuestions")}</Label>
                  {meetingForm.agenda_questions.map((q, i) => (
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
                                setMeetingForm({ ...meetingForm, context_meeting_ids: ids });
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
                      value={meetingForm.max_rounds}
                      onChange={(e) => {
                        const v = e.target.value.replace(/[^0-9]/g, "");
                        setMeetingForm({ ...meetingForm, max_rounds: v });
                      }}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>{t("meetingDescription")}</Label>
                    <Input
                      value={meetingForm.description}
                      onChange={(e) => setMeetingForm({ ...meetingForm, description: e.target.value })}
                      placeholder={t("meetingDescription")}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setShowNewMeeting(false)} disabled={creatingMeeting}>
                    {tc("cancel")}
                  </Button>
                  <Button type="submit" disabled={creatingMeeting}>
                    {creatingMeeting && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
                    {tc("create")}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {meetings.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("noMeetings")}</p>
        ) : (
          <div className="space-y-2">
            {meetings.map((meeting) => (
              <Link
                key={meeting.id}
                href={`/teams/${teamId}/meetings/${meeting.id}`}
              >
                <Card className="hover:border-primary/50 transition-colors cursor-pointer">
                  <CardHeader className="py-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <CardTitle className="text-base flex items-center gap-2">
                        <MessageSquare className="h-4 w-4 shrink-0" />
                        {meeting.title}
                      </CardTitle>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={statusVariant(meeting.status)}>
                          {meeting.status}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {t("round")} {meeting.current_round}/{meeting.max_rounds}
                        </span>
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Edit Agent Dialog — shared with onboarding */}
      <EditAgentDialog
        open={!!editingAgent}
        onOpenChange={(open) => !open && setEditingAgent(null)}
        agent={editingAgent}
        variant="full"
        onSave={handleEditAgentSave}
      />
    </div>
  );
}
