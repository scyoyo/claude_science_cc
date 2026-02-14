"use client";

import ReactMarkdown from "react-markdown";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export function MarkdownContent({ content, className = "" }: MarkdownContentProps) {
  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none break-words ${className}`}>
      <ReactMarkdown
        components={{
          // Keep paragraphs compact
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          // Style code blocks
          pre: ({ children }) => (
            <pre className="bg-muted rounded-md p-3 overflow-x-auto text-xs my-2">
              {children}
            </pre>
          ),
          code: ({ children, className: codeClassName }) => {
            // Inline code (no language class)
            if (!codeClassName) {
              return (
                <code className="bg-muted rounded px-1.5 py-0.5 text-xs font-mono">
                  {children}
                </code>
              );
            }
            return <code className={codeClassName}>{children}</code>;
          },
          // Lists
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-sm">{children}</li>,
          // Headings
          h1: ({ children }) => <h3 className="font-semibold text-base mb-1">{children}</h3>,
          h2: ({ children }) => <h3 className="font-semibold text-sm mb-1">{children}</h3>,
          h3: ({ children }) => <h4 className="font-semibold text-sm mb-1">{children}</h4>,
          // Links
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
              {children}
            </a>
          ),
        }}
      />
    </div>
  );
}
