import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * If content is valid JSON (object or array), return pretty-printed string; otherwise null.
 * Used to detect raw JSON in meeting messages and render as a code block.
 */
export function tryFormatJson(content: string): string | null {
  if (!content || typeof content !== "string") return null;
  const t = content.trim();
  if (t.length < 2 || (t[0] !== "{" && t[0] !== "[")) return null;
  try {
    const parsed = JSON.parse(t);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return null;
  }
}
