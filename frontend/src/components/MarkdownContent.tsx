"use client";

import { useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { FileCode } from "lucide-react";

export interface CodeBlockArtifact {
  id: string;
  filename: string;
}

interface MarkdownContentProps {
  content: string;
  className?: string;
  /** When provided, replace code blocks with clickable file chips (by order: 1st block → artifacts[0], etc.). */
  codeBlockArtifacts?: CodeBlockArtifact[];
  onOpenArtifact?: (id: string) => void;
}

export function MarkdownContent({
  content,
  className = "",
  codeBlockArtifacts,
  onOpenArtifact,
}: MarkdownContentProps) {
  const prevContentRef = useRef<string | null>(null);
  const codeBlockIndexRef = useRef(0);
  if (prevContentRef.current !== content) {
    prevContentRef.current = content;
    codeBlockIndexRef.current = 0;
  }

  const replaceWithArtifactChip = codeBlockArtifacts && codeBlockArtifacts.length > 0 && onOpenArtifact;

  return (
    <div className={`max-w-full min-w-0 break-words overflow-wrap-anywhere [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        children={content}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed break-words max-w-full overflow-wrap-anywhere">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold break-words">{children}</strong>,
          em: ({ children }) => <em className="break-words">{children}</em>,
          pre: ({ children }) => {
            if (replaceWithArtifactChip) {
              const i = codeBlockIndexRef.current++;
              const artifact = codeBlockArtifacts![i];
              if (artifact) {
                return (
                  <span className="inline-flex my-1.5 max-w-full">
                    <button
                      type="button"
                      onClick={() => onOpenArtifact!(artifact.id)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-sm font-medium bg-muted hover:bg-muted/80 border border-border shadow-sm transition-colors max-w-full"
                    >
                      <FileCode className="h-4 w-4 shrink-0" />
                      <span className="truncate max-w-[200px] sm:max-w-[280px]">{artifact.filename}</span>
                    </button>
                  </span>
                );
              }
            }
            return (
              <div className="max-w-full min-w-0 overflow-hidden my-2">
                <pre className="bg-muted/70 rounded-md p-2.5 overflow-x-auto text-xs w-full block">
                  {children}
                </pre>
              </div>
            );
          },
          code: ({ children, className: codeClassName }) => {
            if (!codeClassName) {
              return (
                <code className="bg-muted/70 rounded px-1 py-0.5 text-xs font-mono break-words overflow-wrap-anywhere max-w-full">
                  {children}
                </code>
              );
            }
            return <code className={`${codeClassName} whitespace-pre`}>{children}</code>;
          },
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5 max-w-full min-w-0">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5 max-w-full min-w-0">{children}</ol>,
          li: ({ children }) => <li className="break-words max-w-full overflow-wrap-anywhere">{children}</li>,
          h1: ({ children }) => <p className="font-semibold mb-1 break-words max-w-full">{children}</p>,
          h2: ({ children }) => <p className="font-semibold mb-1 break-words max-w-full">{children}</p>,
          h3: ({ children }) => <p className="font-semibold mb-1 break-words max-w-full">{children}</p>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline break-words overflow-wrap-anywhere max-w-full">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-muted-foreground/30 pl-3 my-2 italic max-w-full min-w-0 break-words">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 max-w-full w-full min-w-0 overflow-hidden rounded-md border border-border">
              <table className="border-collapse text-xs w-full">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-muted/50">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-border">{children}</tr>,
          th: ({ children }) => (
            <th className="border border-border px-2 py-1.5 text-left font-semibold break-words">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border px-2 py-1.5 break-words">
              {children}
            </td>
          ),
          hr: () => <hr className="my-4 border-t border-border" />,
          img: ({ src, alt }) => (
            <img
              src={src}
              alt={alt || ""}
              className="max-w-full h-auto rounded-md my-2"
              loading="lazy"
            />
          ),
          del: ({ children }) => <del className="text-muted-foreground line-through">{children}</del>,
          h4: ({ children }) => <p className="font-semibold mb-1 break-words max-w-full text-sm">{children}</p>,
          h5: ({ children }) => <p className="font-semibold mb-1 break-words max-w-full text-xs">{children}</p>,
          h6: ({ children }) => <p className="font-semibold mb-1 break-words max-w-full text-xs">{children}</p>,
          input: ({ type, checked, disabled }) => {
            if (type === "checkbox") {
              return (
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabled}
                  className="mr-2 align-middle"
                  readOnly
                />
              );
            }
            return <input type={type} />;
          },
        }}
      />
    </div>
  );
}
