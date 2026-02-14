import type {
  Team,
  TeamWithAgents,
  TeamCreate,
  Agent,
  AgentCreate,
  Meeting,
  MeetingWithMessages,
  MeetingUpdate,
  MeetingSummary,
  CodeArtifact,
  OnboardingChatRequest,
  OnboardingChatResponse,
  GenerateTeamRequest,
} from "@/types";
import { getAuthHeaders, getApiBase } from "@/lib/auth";

// Backend paginated response shape
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

const API_BASE =
  typeof window !== "undefined"
    ? getApiBase()
    : (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api");

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...options?.headers,
    },
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
  list: async (): Promise<Team[]> => {
    const res = await fetchAPI<PaginatedResponse<Team>>("/teams/");
    return res.items;
  },
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
  listByTeam: async (teamId: string): Promise<Agent[]> => {
    const res = await fetchAPI<PaginatedResponse<Agent>>(`/agents/team/${teamId}`);
    return res.items;
  },
  create: (data: AgentCreate) =>
    fetchAPI<Agent>("/agents/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentCreate>) =>
    fetchAPI<Agent>(`/agents/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetchAPI<void>(`/agents/${id}`, { method: "DELETE" }),
};

async function fetchRaw(path: string, options?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...getAuthHeaders(),
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res;
}

// Meetings
export const meetingsAPI = {
  list: async (): Promise<Meeting[]> => {
    const res = await fetchAPI<PaginatedResponse<Meeting>>("/meetings/");
    return res.items;
  },
  get: (id: string) => fetchAPI<MeetingWithMessages>(`/meetings/${id}`),
  listByTeam: async (teamId: string): Promise<Meeting[]> => {
    const res = await fetchAPI<PaginatedResponse<Meeting>>(`/meetings/team/${teamId}`);
    return res.items;
  },
  create: (data: { team_id: string; title: string; description?: string; max_rounds?: number }) =>
    fetchAPI<Meeting>("/meetings/", { method: "POST", body: JSON.stringify(data) }),
  update: (id: string, data: MeetingUpdate) =>
    fetchAPI<Meeting>(`/meetings/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetchAPI<void>(`/meetings/${id}`, { method: "DELETE" }),
  clone: (id: string) =>
    fetchAPI<Meeting>(`/meetings/${id}/clone`, { method: "POST" }),
  summary: (id: string) =>
    fetchAPI<MeetingSummary>(`/meetings/${id}/summary`),
  transcript: async (id: string): Promise<Blob> => {
    const res = await fetchRaw(`/meetings/${id}/transcript`);
    return res.blob();
  },
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
  runBackground: (meetingId: string, rounds: number = 1, topic?: string) =>
    fetchAPI<{ meeting_id: string; status: string; rounds: number }>(`/meetings/${meetingId}/run-background`, {
      method: "POST",
      body: JSON.stringify({ rounds, topic }),
    }),
  status: (meetingId: string) =>
    fetchAPI<{
      meeting_id: string;
      status: string;
      current_round: number;
      max_rounds: number;
      message_count: number;
      background_running: boolean;
    }>(`/meetings/${meetingId}/status`),
};

// Artifacts
export const artifactsAPI = {
  listByMeeting: async (meetingId: string): Promise<CodeArtifact[]> => {
    const res = await fetchAPI<PaginatedResponse<CodeArtifact>>(`/artifacts/meeting/${meetingId}`);
    return res.items;
  },
  get: (id: string) => fetchAPI<CodeArtifact>(`/artifacts/${id}`),
  create: (data: { meeting_id: string; filename: string; language: string; content: string; description?: string }) =>
    fetchAPI<CodeArtifact>("/artifacts/", { method: "POST", body: JSON.stringify(data) }),
  extract: (meetingId: string) =>
    fetchAPI<CodeArtifact[]>(`/artifacts/meeting/${meetingId}/extract`, { method: "POST" }),
  delete: (id: string) =>
    fetchAPI<void>(`/artifacts/${id}`, { method: "DELETE" }),
};

// Export
export const exportAPI = {
  zip: async (meetingId: string): Promise<Blob> => {
    const res = await fetchRaw(`/export/meeting/${meetingId}/zip`);
    return res.blob();
  },
  notebook: async (meetingId: string): Promise<Blob> => {
    const res = await fetchRaw(`/export/meeting/${meetingId}/notebook`);
    return res.blob();
  },
  github: (meetingId: string) =>
    fetchAPI<{ project_name: string; files: Array<{ path: string; content: string }> }>(`/export/meeting/${meetingId}/github`),
};

// Onboarding
export const onboardingAPI = {
  chat: (data: OnboardingChatRequest) =>
    fetchAPI<OnboardingChatResponse>("/onboarding/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  generateTeam: (data: GenerateTeamRequest) =>
    fetchAPI<TeamWithAgents>("/onboarding/generate-team", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// LLM
export interface APIKeyInfo {
  id: string;
  provider: string;
  is_active: boolean;
  key_preview: string;
  created_at: string;
}

export const llmAPI = {
  providers: () => fetchAPI<{ providers: string[] }>("/llm/providers"),
  listKeys: () => fetchAPI<APIKeyInfo[]>("/llm/api-keys"),
  addKey: (provider: string, api_key: string) =>
    fetchAPI<APIKeyInfo>("/llm/api-keys", {
      method: "POST",
      body: JSON.stringify({ provider, api_key }),
    }),
  deleteKey: (id: string) =>
    fetchAPI<void>(`/llm/api-keys/${id}`, { method: "DELETE" }),
};
