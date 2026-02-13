import type {
  Team,
  TeamWithAgents,
  TeamCreate,
  Agent,
  AgentCreate,
  Meeting,
  MeetingWithMessages,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Teams
export const teamsAPI = {
  list: () => fetchAPI<Team[]>("/teams/"),
  get: (id: string) => fetchAPI<TeamWithAgents>(`/teams/${id}`),
  create: (data: TeamCreate) =>
    fetchAPI<Team>("/teams/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<TeamCreate>) =>
    fetchAPI<Team>(`/teams/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetchAPI<void>(`/teams/${id}`, { method: "DELETE" }),
};

// Agents
export const agentsAPI = {
  get: (id: string) => fetchAPI<Agent>(`/agents/${id}`),
  listByTeam: (teamId: string) => fetchAPI<Agent[]>(`/agents/team/${teamId}`),
  create: (data: AgentCreate) =>
    fetchAPI<Agent>("/agents/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentCreate>) =>
    fetchAPI<Agent>(`/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetchAPI<void>(`/agents/${id}`, { method: "DELETE" }),
};

// Meetings
export const meetingsAPI = {
  get: (id: string) => fetchAPI<MeetingWithMessages>(`/meetings/${id}`),
  listByTeam: (teamId: string) => fetchAPI<Meeting[]>(`/meetings/team/${teamId}`),
  create: (data: { team_id: string; title: string; description?: string; max_rounds?: number }) =>
    fetchAPI<Meeting>("/meetings/", { method: "POST", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetchAPI<void>(`/meetings/${id}`, { method: "DELETE" }),
  addMessage: (meetingId: string, content: string) =>
    fetchAPI<MeetingWithMessages>(`/meetings/${meetingId}/message`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  run: (meetingId: string, rounds: number = 1, topic?: string) =>
    fetchAPI<MeetingWithMessages>(`/meetings/${meetingId}/run`, {
      method: "POST",
      body: JSON.stringify({ rounds, topic }),
    }),
};
