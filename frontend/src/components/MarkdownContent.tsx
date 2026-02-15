"use client";

import { useRef } from "react";
import ReactMarkdown from "react-markdown";
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
    <div className={`max-w-full break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 ${className}`}>
      <ReactMarkdown
        children={content}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed break-words">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em>{children}</em>,
          pre: ({ children }) => {
            if (replaceWithArtifactChip) {
              const i = codeBlockIndexRef.current++;
              const artifact = codeBlockArtifacts![i];
              if (artifact) {
                return (
                  <span className="inline-flex my-1.5">
                    <button
                      type="button"
                      onClick={() => onOpenArtifact!(artifact.id)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-sm font-medium bg-muted hover:bg-muted/80 border border-border shadow-sm transition-colors"
                    >
                      <FileCode className="h-4 w-4 shrink-0" />
                      <span className="truncate max-w-[200px] sm:max-w-[280px]">{artifact.filename}</span>
                    </button>
                  </span>
                );
              }
            }
            return (
              <pre className="bg-muted/70 rounded-md p-2.5 overflow-x-auto text-xs my-2 max-w-full">
                {children}
              </pre>
            );
          },
          code: ({ children, className: codeClassName }) => {
            if (!codeClassName) {
              return (
                <code className="bg-muted/70 rounded px-1 py-0.5 text-xs font-mono">
                  {children}
                </code>
              );
            }
            return <code className={codeClassName}>{children}</code>;
          },
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          h1: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
          h2: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
          h3: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-muted-foreground/30 pl-3 my-2 italic">
              {children}
            </blockquote>
          ),
        }}
      />
    </div>
  );
}
