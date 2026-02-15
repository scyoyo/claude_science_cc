/**
 * Shared model options for agent creation/editing.
 * Value = API model identifier, label = display name.
 * Ordered by generation (newest first within each provider).
 */
export const MODEL_OPTIONS: { value: string; label: string }[] = [
  // OpenAI — latest first
  { value: "gpt-5.2", label: "GPT-5.2" },
  { value: "gpt-5", label: "GPT-5" },
  { value: "gpt-4.1", label: "GPT-4.1" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
  { value: "o1", label: "o1" },
  { value: "o1-mini", label: "o1 Mini" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  { value: "gpt-4", label: "GPT-4" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
  // Anthropic — latest first
  { value: "claude-opus-4.6", label: "Claude Opus 4.6" },
  { value: "claude-opus-4-5-20250929", label: "Claude Opus 4.5" },
  { value: "claude-sonnet-4-5-20250929", label: "Claude Sonnet 4.5" },
  { value: "claude-opus-4-20250514", label: "Claude Opus 4" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet" },
  { value: "claude-3-opus-20240229", label: "Claude 3 Opus" },
  { value: "claude-3-sonnet-20240229", label: "Claude 3 Sonnet" },
  // DeepSeek
  { value: "deepseek-chat", label: "DeepSeek Chat" },
  { value: "deepseek-reasoner", label: "DeepSeek R1" },
];

export const DEFAULT_MODEL = "gpt-4.1";

/** Provider for a model id (matches backend detect_provider). */
const MODEL_PROVIDER_MAP: [string, string][] = [
  ["gpt-", "openai"],
  ["o1", "openai"],
  ["claude-", "anthropic"],
  ["deepseek-", "deepseek"],
];

export function getProviderForModel(model: string): string | null {
  if (!model) return null;
  for (const [prefix, provider] of MODEL_PROVIDER_MAP) {
    if (model.startsWith(prefix)) return provider;
  }
  return null;
}

/** Display name for a model id (e.g. claude-sonnet-4-5-20250929 -> "Claude Sonnet 4.5"). */
export function getModelLabel(value: string): string {
  if (!value) return value;
  const opt = MODEL_OPTIONS.find((o) => o.value === value);
  return opt ? opt.label : value;
}
