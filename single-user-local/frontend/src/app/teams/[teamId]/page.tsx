"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { teamsAPI, agentsAPI, meetingsAPI } from "@/lib/api";
import type { TeamWithAgents, Agent, Meeting } from "@/types";

export default function TeamDetailPage() {
  const params = useParams();
  const teamId = params.teamId as string;

  const [team, setTeam] = useState<TeamWithAgents | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [showNewMeeting, setShowNewMeeting] = useState(false);

  // Agent form
  const [agentForm, setAgentForm] = useState({
    name: "",
    title: "",
    expertise: "",
    goal: "",
    role: "",
    model: "gpt-4",
  });

  // Meeting form
  const [meetingTitle, setMeetingTitle] = useState("");

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
    if (!confirm("Delete this agent?")) return;
    try {
      await agentsAPI.delete(agentId);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete agent");
    }
  };

  const handleCreateMeeting = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!meetingTitle.trim()) return;
    try {
      await meetingsAPI.create({ team_id: teamId, title: meetingTitle });
      setMeetingTitle("");
      setShowNewMeeting(false);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create meeting");
    }
  };

  if (loading) return <p className="text-gray-500">Loading...</p>;
  if (!team) return <p className="text-red-500">Team not found</p>;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <Link href="/teams" className="text-sm text-blue-600 hover:text-blue-800">
          &larr; Back to Teams
        </Link>
        <div className="mt-2 flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900">{team.name}</h1>
          <Link
            href={`/teams/${teamId}/editor`}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
          >
            Visual Editor
          </Link>
        </div>
        {team.description && (
          <p className="mt-1 text-gray-600">{team.description}</p>
        )}
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Agents Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Agents ({team.agents.length})
          </h2>
          <button
            onClick={() => setShowAddAgent(!showAddAgent)}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
          >
            {showAddAgent ? "Cancel" : "Add Agent"}
          </button>
        </div>

        {showAddAgent && (
          <form onSubmit={handleCreateAgent} className="mb-4 p-4 bg-white rounded-lg border border-gray-200 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text"
                value={agentForm.name}
                onChange={(e) => setAgentForm({ ...agentForm, name: e.target.value })}
                placeholder="Agent name"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <input
                type="text"
                value={agentForm.title}
                onChange={(e) => setAgentForm({ ...agentForm, title: e.target.value })}
                placeholder="Title (e.g., Senior Researcher)"
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <input
              type="text"
              value={agentForm.expertise}
              onChange={(e) => setAgentForm({ ...agentForm, expertise: e.target.value })}
              placeholder="Expertise"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <input
              type="text"
              value={agentForm.goal}
              onChange={(e) => setAgentForm({ ...agentForm, goal: e.target.value })}
              placeholder="Goal"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <input
              type="text"
              value={agentForm.role}
              onChange={(e) => setAgentForm({ ...agentForm, role: e.target.value })}
              placeholder="Role"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <div className="flex items-center gap-3">
              <select
                value={agentForm.model}
                onChange={(e) => setAgentForm({ ...agentForm, model: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                <option value="deepseek-chat">DeepSeek Chat</option>
              </select>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Create Agent
              </button>
            </div>
          </form>
        )}

        {team.agents.length === 0 ? (
          <p className="text-gray-500 text-sm">No agents yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {team.agents.map((agent) => (
              <div
                key={agent.id}
                className="p-4 bg-white rounded-lg border border-gray-200"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      {agent.name}
                      {agent.is_mirror && (
                        <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded">
                          Mirror
                        </span>
                      )}
                    </h3>
                    <p className="text-sm text-gray-600">{agent.title}</p>
                  </div>
                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                    {agent.model}
                  </span>
                </div>
                <div className="mt-2 space-y-1 text-sm text-gray-500">
                  <p><span className="font-medium">Expertise:</span> {agent.expertise}</p>
                  <p><span className="font-medium">Goal:</span> {agent.goal}</p>
                </div>
                <div className="mt-3 flex justify-end">
                  <button
                    onClick={() => handleDeleteAgent(agent.id)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Meetings Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            Meetings ({meetings.length})
          </h2>
          <button
            onClick={() => setShowNewMeeting(!showNewMeeting)}
            className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700"
          >
            {showNewMeeting ? "Cancel" : "New Meeting"}
          </button>
        </div>

        {showNewMeeting && (
          <form onSubmit={handleCreateMeeting} className="mb-4 p-4 bg-white rounded-lg border border-gray-200 flex gap-3">
            <input
              type="text"
              value={meetingTitle}
              onChange={(e) => setMeetingTitle(e.target.value)}
              placeholder="Meeting title"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
              autoFocus
            />
            <button
              type="submit"
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              Create
            </button>
          </form>
        )}

        {meetings.length === 0 ? (
          <p className="text-gray-500 text-sm">No meetings yet.</p>
        ) : (
          <div className="space-y-2">
            {meetings.map((meeting) => (
              <Link
                key={meeting.id}
                href={`/teams/${teamId}/meetings/${meeting.id}`}
                className="block p-4 bg-white rounded-lg border border-gray-200 hover:border-green-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-gray-900">{meeting.title}</h3>
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      meeting.status === "completed"
                        ? "bg-green-100 text-green-700"
                        : meeting.status === "running"
                        ? "bg-yellow-100 text-yellow-700"
                        : meeting.status === "failed"
                        ? "bg-red-100 text-red-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {meeting.status}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1">
                  Round {meeting.current_round}/{meeting.max_rounds}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
