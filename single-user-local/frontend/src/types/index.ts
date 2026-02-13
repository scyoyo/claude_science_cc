// Backend API types matching Pydantic schemas

// Auth
export interface User {
  id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
}

export interface Team {
  id: string;
  name: string;
  description: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}

export interface TeamWithAgents extends Team {
  agents: Agent[];
}

export interface TeamCreate {
  name: string;
  description?: string;
  is_public?: boolean;
}

export interface Agent {
  id: string;
  team_id: string;
  name: string;
  title: string;
  expertise: string;
  goal: string;
  role: string;
  system_prompt: string;
  model: string;
  model_params: Record<string, unknown>;
  position_x: number;
  position_y: number;
  is_mirror: boolean;
  primary_agent_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  team_id: string;
  name: string;
  title: string;
  expertise: string;
  goal: string;
  role: string;
  model: string;
  model_params?: Record<string, unknown>;
}

export interface Meeting {
  id: string;
  team_id: string;
  title: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  max_rounds: number;
  current_round: number;
  created_at: string;
  updated_at: string;
}

export interface MeetingMessage {
  id: string;
  meeting_id: string;
  agent_id: string | null;
  role: string;
  agent_name: string | null;
  content: string;
  round_number: number;
  created_at: string;
}

export interface MeetingWithMessages extends Meeting {
  messages: MeetingMessage[];
}
