"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileCode } from "lucide-react";

export interface CodeFileItem {
  path: string;
  content: string;
  language?: string;
}

interface CodeFilesBlockProps {
  files: CodeFileItem[];
  className?: string;
}

/** Renders a list of code files (path + expandable content) from JSON agent output. */
export function CodeFilesBlock({ files, className = "" }: CodeFilesBlockProps) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));

  const toggle = (i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  if (!files.length) return null;

  return (
    <div className={`space-y-1 ${className}`}>
      {files.map((file, i) => (
        <div
          key={file.path + i}
          className="rounded-md border border-border bg-muted/50 overflow-hidden"
        >
          <button
            type="button"
            onClick={() => toggle(i)}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-sm font-medium hover:bg-muted/80 transition-colors"
          >
            {expanded.has(i) ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <FileCode className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate font-mono text-xs">{file.path}</span>
          </button>
          {expanded.has(i) && (
            <div className="max-h-[320px] overflow-auto border-t border-border">
              <pre className="p-2.5 text-xs font-mono whitespace-pre wrap break-words bg-muted/30 m-0">
                {file.content}
              </pre>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function isFileLike(f: unknown): f is { path: unknown; content: unknown; language?: unknown } {
  return !!f && typeof f === "object" && "path" in (f as object) && "content" in (f as object);
}

function toFiles(data: unknown): CodeFileItem[] {
  if (!data || typeof data !== "object" || !Array.isArray((data as { files?: unknown }).files))
    return [];
  const arr = (data as { files: unknown[] }).files;
  return arr
    .filter(isFileLike)
    .map((f) => ({
      path: String(f.path || ""),
      content: String(f.content ?? ""),
      language: f.language != null ? String(f.language) : undefined,
    }))
    .filter((f) => f.path);
}

/**
 * Try to parse content for JSON with "files" array.
 * Returns { files, restContent } if valid, else null.
 */
export function parseCodeFilesJson(content: string): {
  files: CodeFileItem[];
  restContent: string;
} | null {
  if (!content || typeof content !== "string") return null;
  const text = content.trim();

  // 1) Strip ```json ... ``` if present
  const jsonFence = /```(?:json)?\s*\n([\s\S]*?)```/;
  const fenceMatch = text.match(jsonFence);
  if (fenceMatch) {
    try {
      const data = JSON.parse(fenceMatch[1].trim());
      const files = toFiles(data);
      if (files.length > 0) {
        const rest = text.replace(fenceMatch[0], "").trim();
        return { files, restContent: rest };
      }
    } catch {
      // ignore
    }
  }

  // 2) Try parse whole content as JSON
  try {
    const data = JSON.parse(text);
    const files = toFiles(data);
    if (files.length > 0) return { files, restContent: "" };
  } catch {
    // ignore
  }

  // 3) Find {...} containing "files", with text before/after. Match braces while skipping inside strings.
  const idx = text.indexOf("files");
  if (idx === -1) return null;
  let start = text.lastIndexOf("{", idx);
  if (start === -1) return null;
  const end = findJsonObjectEnd(text, start);
  if (end === -1) return null;
  try {
    const data = JSON.parse(text.slice(start, end + 1));
    const files = toFiles(data);
    if (files.length > 0) {
      const rest = (text.slice(0, start).trim() + " " + text.slice(end + 1).trim()).trim();
      return { files, restContent: rest };
    }
  } catch {
    // ignore
  }
  return null;
}

/**
 * Find the index of the closing "}" for the JSON object starting at start.
 * Skips braces inside double-quoted strings (handles \", \\, etc.).
 */
function findJsonObjectEnd(text: string, start: number): number {
  let depth = 0;
  let i = start;
  const n = text.length;
  while (i < n) {
    const ch = text[i];
    if (ch === '"') {
      i++;
      while (i < n) {
        const c = text[i];
        if (c === "\\") {
          i += 2;
          continue;
        }
        if (c === '"') {
          i++;
          break;
        }
        i++;
      }
      continue;
    }
    if (ch === "{") {
      depth++;
      i++;
      continue;
    }
    if (ch === "}") {
      depth--;
      if (depth === 0) return i;
      i++;
      continue;
    }
    i++;
  }
  return -1;
}
