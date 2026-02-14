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

export type MeetingType = "team" | "individual" | "merge";
export type AgendaStrategy = "manual" | "ai_auto" | "onboarding" | "agent_voting" | "chain";

export interface Meeting {
  id: string;
  team_id: string;
  title: string;
  description: string;
  agenda: string;
  agenda_questions: string[];
  agenda_rules: string[];
  output_type: string;
  context_meeting_ids: string[];
  participant_agent_ids?: string[];
  meeting_type: MeetingType;
  individual_agent_id?: string | null;
  source_meeting_ids: string[];
  parent_meeting_id?: string | null;
  rewrite_feedback?: string;
  agenda_strategy: AgendaStrategy;
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

export interface MeetingCreate {
  team_id: string;
  title: string;
  description?: string;
  agenda?: string;
  agenda_questions?: string[];
  agenda_rules?: string[];
  output_type?: string;
  context_meeting_ids?: string[];
  participant_agent_ids?: string[];
  meeting_type?: MeetingType;
  individual_agent_id?: string;
  source_meeting_ids?: string[];
  parent_meeting_id?: string;
  rewrite_feedback?: string;
  agenda_strategy?: AgendaStrategy;
  max_rounds?: number;
}

export interface MeetingUpdate {
  title?: string;
  description?: string;
  agenda?: string;
  agenda_questions?: string[];
  agenda_rules?: string[];
  output_type?: string;
  max_rounds?: number;
}

export interface MeetingSummary {
  meeting_id: string;
  title: string;
  total_rounds: number;
  total_messages: number;
  participants: string[];
  key_points: string[];
  status: string;
}

export interface CodeArtifact {
  id: string;
  meeting_id: string;
  filename: string;
  language: string;
  content: string;
  description: string;
  version: number;
  created_at: string;
  updated_at: string;
}

// Onboarding
export type OnboardingStage =
  | "problem"
  | "clarification"
  | "team_suggestion"
  | "mirror_config"
  | "complete";

export interface OnboardingChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface OnboardingChatRequest {
  /** Optional: when omitted, backend infers stage from context + conversation (semantic flow). */
  stage?: OnboardingStage;
  message: string;
  conversation_history: OnboardingChatMessage[];
  context: Record<string, unknown>;
  /** System locale fallback for agent response language (e.g. "en", "zh"). */
  locale?: string;
}

export interface OnboardingChatResponse {
  stage: OnboardingStage;
  next_stage: OnboardingStage | null;
  message: string;
  data: Record<string, unknown>;
}

export interface AgentSuggestion {
  name: string;
  title: string;
  expertise: string;
  goal: string;
  role: string;
  model: string;
}

export interface TeamSuggestion {
  team_name: string;
  team_description: string;
  agents: AgentSuggestion[];
}

export interface MirrorConfig {
  enabled: boolean;
  mirror_model: string;
  agents_to_mirror: string[];
}

export interface GenerateTeamRequest {
  team_name: string;
  team_description: string;
  agents: AgentSuggestion[];
  mirror_config?: MirrorConfig;
}

// Dashboard
export interface DashboardRecentMeeting {
  id: string;
  title: string;
  team_id: string;
  team_name: string;
  status: string;
  current_round: number;
  max_rounds: number;
  updated_at: string;
}

export interface DashboardTeamOverview {
  id: string;
  name: string;
  description: string | null;
  agent_count: number;
  meeting_count: number;
  created_at: string;
}

export interface DashboardStats {
  total_teams: number;
  total_agents: number;
  total_meetings: number;
  completed_meetings: number;
  total_artifacts: number;
  total_messages: number;
  recent_meetings: DashboardRecentMeeting[];
  teams_overview: DashboardTeamOverview[];
}

// Agent Templates
export interface AgentTemplate {
  id: string;
  name: string;
  title: string;
  expertise: string;
  goal: string;
  role: string;
  model: string;
  category: string;
}

// Webhooks
export interface Webhook {
  id: string;
  url: string;
  events: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebhookCreate {
  url: string;
  events: string[];
  secret?: string;
}

export interface WebhookUpdate {
  url?: string;
  events?: string[];
  is_active?: boolean;
}

// Meeting Comparison
export interface MeetingComparisonItem {
  id: string;
  title: string;
  status: string;
  rounds: number;
  max_rounds: number;
  message_count: number;
  participants: string[];
}

export interface MeetingComparison {
  meetings: MeetingComparisonItem[];
  shared_participants: string[];
  unique_to_first: string[];
  unique_to_second: string[];
}

// Team Stats
export interface TeamStats {
  team_id: string;
  agent_count: number;
  meeting_count: number;
  completed_meetings: number;
  message_count: number;
  artifact_count: number;
}

// Agent Metrics
export interface AgentMetrics {
  agent_id: string;
  total_messages: number;
  total_meetings: number;
  avg_message_length: number;
  rounds_participated: number;
}

// Agenda Strategy Types
export interface AgendaAutoResponse {
  agenda: string;
  questions: string[];
  rules: string[];
  suggested_rounds: number;
}

export interface AgentProposal {
  agent_name: string;
  proposals: string[];
}

export interface AgentVotingResponse {
  proposals: AgentProposal[];
  merged_agenda: string;
}

export interface RecommendStrategyResponse {
  recommended: string;
  reasoning: string;
}

// Batch Run / Rewrite Types
export interface BatchMeetingRunResponse {
  iteration_meeting_ids: string[];
  merge_meeting_id: string | null;
}

export interface ContextPreviewResponse {
  contexts: Array<{ title: string; summary: string }>;
  total_chars: number;
}
