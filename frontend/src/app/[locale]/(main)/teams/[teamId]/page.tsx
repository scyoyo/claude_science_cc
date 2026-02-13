"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { teamsAPI, agentsAPI, meetingsAPI } from "@/lib/api";
import type { TeamWithAgents, Meeting } from "@/types";
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
import { ArrowLeft, Plus, Trash2, Workflow, MessageSquare, Bot } from "lucide-react";

export default function TeamDetailPage() {
  const params = useParams();
  const teamId = params.teamId as string;
  const t = useTranslations("teamDetail");
  const tc = useTranslations("common");

  const [team, setTeam] = useState<TeamWithAgents | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [showNewMeeting, setShowNewMeeting] = useState(false);

  const [agentForm, setAgentForm] = useState({
    name: "",
    title: "",
    expertise: "",
    goal: "",
    role: "",
    model: "gpt-4",
  });
  const [meetingForm, setMeetingForm] = useState({ title: "", description: "", max_rounds: 5 });

  const loadData = async () => {
    try {
      setLoading(true);
      const [teamData, meetingsData] = await Promise.all([
        teamsAPI.get(teamId),
        meetingsAPI.listByTeam(teamId),
      ]);
      setTeam(teamData);
      setMeetings(meetingsData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load team");
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
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create agent");
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    if (!confirm(t("deleteAgent"))) return;
    try {
      await agentsAPI.delete(agentId);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete agent");
    }
  };

  const handleCreateMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!meetingForm.title.trim()) return;
    try {
      await meetingsAPI.create({
        team_id: teamId,
        title: meetingForm.title,
        description: meetingForm.description || undefined,
        max_rounds: meetingForm.max_rounds,
      });
      setMeetingForm({ title: "", description: "", max_rounds: 5 });
      setShowNewMeeting(false);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting");
    }
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
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-bold">{team.name}</h1>
          <Button asChild size="sm" variant="outline">
            <Link href={`/teams/${teamId}/editor`}>
              <Workflow className="h-4 w-4 mr-1" />
              {t("visualEditor")}
            </Link>
          </Button>
        </div>
        {team.description && (
          <p className="mt-1 text-muted-foreground">{team.description}</p>
        )}
      </div>

      {error && (
        <div className="p-3 bg-destructive/10 text-destructive rounded-lg text-sm">{error}</div>
      )}

      {/* Agents Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {t("agents")} ({team.agents.length})
          </h2>
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
                    <SelectItem value="gpt-4">GPT-4</SelectItem>
                    <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                    <SelectItem value="claude-3-opus-20240229">Claude 3 Opus</SelectItem>
                    <SelectItem value="claude-3-sonnet-20240229">Claude 3 Sonnet</SelectItem>
                    <SelectItem value="deepseek-chat">DeepSeek Chat</SelectItem>
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

        {team.agents.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("noAgents")}</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {team.agents.map((agent) => (
              <Card key={agent.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <Bot className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <CardTitle className="text-base flex items-center gap-2">
                          {agent.name}
                          {agent.is_mirror && (
                            <Badge variant="secondary">{t("mirror")}</Badge>
                          )}
                        </CardTitle>
                        <CardDescription>{agent.title}</CardDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{agent.model}</Badge>
                      <Button
                        variant="ghost"
                        size="icon-xs"
                        onClick={() => handleDeleteAgent(agent.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1 text-sm text-muted-foreground">
                    <p><span className="font-medium text-foreground">{t("expertise")}:</span> {agent.expertise}</p>
                    <p><span className="font-medium text-foreground">{t("goal")}:</span> {agent.goal}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Meetings Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {t("meetings")} ({meetings.length})
          </h2>
          <Dialog open={showNewMeeting} onOpenChange={setShowNewMeeting}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4 mr-1" />
                {t("addMeeting")}
              </Button>
            </DialogTrigger>
            <DialogContent>
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
                <div className="space-y-2">
                  <Label>{t("meetingDescription")}</Label>
                  <Textarea
                    value={meetingForm.description}
                    onChange={(e) => setMeetingForm({ ...meetingForm, description: e.target.value })}
                    placeholder={t("meetingDescription")}
                    rows={3}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t("meetingMaxRounds")}</Label>
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={meetingForm.max_rounds}
                    onChange={(e) => setMeetingForm({ ...meetingForm, max_rounds: parseInt(e.target.value) || 5 })}
                  />
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setShowNewMeeting(false)}>
                    {tc("cancel")}
                  </Button>
                  <Button type="submit">{tc("create")}</Button>
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
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base flex items-center gap-2">
                        <MessageSquare className="h-4 w-4" />
                        {meeting.title}
                      </CardTitle>
                      <div className="flex items-center gap-2">
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
    </div>
  );
}
