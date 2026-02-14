/**
 * Shared model options for agent creation/editing.
 * Value = API model identifier, label = display name.
 */
export const MODEL_OPTIONS: { value: string; label: string }[] = [
  // OpenAI
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  { value: "gpt-4", label: "GPT-4" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
  { value: "o1", label: "o1" },
  { value: "o1-mini", label: "o1 Mini" },
  { value: "gpt-4.1", label: "GPT-4.1" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
  { value: "gpt-5", label: "GPT-5" },
  { value: "gpt-5.2", label: "GPT-5.2" },
  // Anthropic
  { value: "claude-opus-4-20250514", label: "Claude Opus 4" },
  { value: "claude-opus-4-5-20250929", label: "Claude Opus 4.5" },
  { value: "claude-opus-4.6", label: "Claude Opus 4.6" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "claude-sonnet-4-5-20250929", label: "Claude Sonnet 4.5" },
  { value: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet" },
  { value: "claude-3-opus-20240229", label: "Claude 3 Opus" },
  { value: "claude-3-sonnet-20240229", label: "Claude 3 Sonnet" },
  // DeepSeek (model name is deepseek-chat, not "deepseek")
  { value: "deepseek-chat", label: "DeepSeek Chat" },
  { value: "deepseek-reasoner", label: "DeepSeek R1" },
];

export const DEFAULT_MODEL = "gpt-4";
