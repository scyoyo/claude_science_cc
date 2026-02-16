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
 * Repair JSON string by replacing literal newlines inside double-quoted strings with \\n
 * so that JSON.parse can accept it (LLM often outputs unescaped newlines in "content").
 */
function repairJsonLiteralNewlines(jsonStr: string): string {
  let out = "";
  let inString = false;
  let escapeNext = false;
  for (let i = 0; i < jsonStr.length; i++) {
    const ch = jsonStr[i];
    if (escapeNext) {
      escapeNext = false;
      out += ch;
      continue;
    }
    if (ch === "\\") {
      escapeNext = true;
      out += ch;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      out += ch;
      continue;
    }
    if (inString && (ch === "\n" || ch === "\r")) {
      out += ch === "\r" ? "\\r" : "\\n";
      continue;
    }
    out += ch;
  }
  return out;
}

function tryParseFilesJson(jsonStr: string): ReturnType<typeof toFiles> | null {
  try {
    const data = JSON.parse(jsonStr) as { files?: unknown };
    const files = toFiles(data);
    return files.length > 0 ? files : null;
  } catch {
    return null;
  }
}

/**
 * Extract complete file objects from truncated JSON like `{"files": [{...}, {...}, <truncated>`.
 * Walks the string scanning for balanced `{...}` objects inside the `"files": [` array,
 * skipping content inside JSON strings (handles `\"`, `\\`, etc.).
 */
function tryParsePartialFilesJson(jsonStr: string): CodeFileItem[] | null {
  const arrIdx = jsonStr.indexOf("[");
  if (arrIdx === -1) return null;
  const files: CodeFileItem[] = [];
  let i = arrIdx + 1;
  const n = jsonStr.length;
  while (i < n) {
    // Skip whitespace and commas between objects
    const ch = jsonStr[i];
    if (ch === " " || ch === "\n" || ch === "\r" || ch === "\t" || ch === ",") { i++; continue; }
    if (ch === "]") break; // end of array
    if (ch !== "{") { i++; continue; }
    // Found start of an object — find its balanced end
    const objStart = i;
    const objEnd = findJsonObjectEnd(jsonStr, objStart);
    if (objEnd === -1) break; // truncated — stop here
    const objStr = jsonStr.slice(objStart, objEnd + 1);
    try {
      const obj = JSON.parse(objStr) as Record<string, unknown>;
      if (obj.path && typeof obj.content === "string") {
        files.push({
          path: String(obj.path),
          content: obj.content,
          language: obj.language != null ? String(obj.language) : undefined,
        });
      }
    } catch {
      // Try with repair
      try {
        const obj = JSON.parse(repairJsonLiteralNewlines(objStr)) as Record<string, unknown>;
        if (obj.path && typeof obj.content === "string") {
          files.push({
            path: String(obj.path),
            content: obj.content,
            language: obj.language != null ? String(obj.language) : undefined,
          });
        }
      } catch { /* skip malformed object */ }
    }
    i = objEnd + 1;
  }
  return files.length > 0 ? files : null;
}

/**
 * Try to parse content for JSON with "files" array.
 * Returns { files, restContent } if valid, else null.
 * Tolerates literal newlines inside "content" (repairs before parse when needed).
 * Also handles truncated JSON (LLM hit token limit) by extracting complete file objects.
 */
export function parseCodeFilesJson(content: string): {
  files: CodeFileItem[];
  restContent: string;
} | null {
  if (!content || typeof content !== "string") return null;
  const text = content.trim();

  // 1) Strip ```json ... ``` if present (closed fence)
  const jsonFence = /```(?:json)?\s*\n([\s\S]*?)```/;
  const fenceMatch = text.match(jsonFence);
  if (fenceMatch) {
    const raw = fenceMatch[1].trim();
    let files = tryParseFilesJson(raw);
    if (!files) files = tryParseFilesJson(repairJsonLiteralNewlines(raw));
    if (files && files.length > 0) {
      const rest = text.replace(fenceMatch[0], "").trim();
      return { files, restContent: rest };
    }
  }

  // 2) Try parse whole content as JSON
  let files = tryParseFilesJson(text);
  if (!files) files = tryParseFilesJson(repairJsonLiteralNewlines(text));
  if (files && files.length > 0) return { files, restContent: "" };

  // 3) Find {...} containing "files", with text before/after. Match braces while skipping inside strings.
  const idx = text.indexOf("files");
  if (idx === -1) return null;
  let start = text.lastIndexOf("{", idx);
  if (start === -1) return null;
  const end = findJsonObjectEnd(text, start);
  if (end !== -1) {
    const segment = text.slice(start, end + 1);
    files = tryParseFilesJson(segment);
    if (!files) files = tryParseFilesJson(repairJsonLiteralNewlines(segment));
    if (files && files.length > 0) {
      const rest = (text.slice(0, start).trim() + " " + text.slice(end + 1).trim()).trim();
      return { files, restContent: rest };
    }
  }

  // 4) Truncated JSON: braces not balanced (LLM hit token limit).
  //    Extract whatever complete file objects exist before the truncation point.
  //    Handles both unclosed ```json fences and bare truncated JSON.
  const truncated = text.slice(start);
  if (truncated.includes('"files"')) {
    const partial = tryParsePartialFilesJson(truncated);
    if (partial && partial.length > 0) {
      const rest = text.slice(0, start).trim();
      return { files: partial, restContent: rest };
    }
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
