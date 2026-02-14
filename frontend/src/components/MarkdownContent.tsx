"use client";

import ReactMarkdown from "react-markdown";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  return (
    <div className={`max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 ${className}`}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em>{children}</em>,
          pre: ({ children }) => (
            <pre className="bg-muted/70 rounded-md p-2.5 overflow-x-auto text-xs my-2">
              {children}
            </pre>
          ),
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
