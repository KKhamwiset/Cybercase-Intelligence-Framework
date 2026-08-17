"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessageMarkdownProps {
  content: string;
}

export function ChatMessageMarkdown({ content }: ChatMessageMarkdownProps) {
  return (
    <div className="markdown-content text-sm leading-relaxed text-ink sm:text-base">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-5 mb-3 text-xl font-extrabold tracking-tight text-ink sm:text-2xl first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-4 mb-2 text-lg font-bold tracking-tight text-ink sm:text-xl first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-3.5 mb-2 text-base font-bold text-ink sm:text-lg first:mt-0">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-3 mb-1.5 text-sm font-bold text-ink sm:text-base first:mt-0">
              {children}
            </h4>
          ),
          h5: ({ children }) => (
            <h5 className="mt-2 mb-1 text-sm font-semibold text-ink-secondary first:mt-0">
              {children}
            </h5>
          ),
          h6: ({ children }) => (
            <h6 className="mt-2 mb-1 text-xs font-mono font-bold uppercase tracking-wider text-ink-secondary first:mt-0">
              {children}
            </h6>
          ),
          p: ({ children }) => (
            <p className="mb-3.5 text-sm leading-relaxed text-ink break-words sm:text-base last:mb-0">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="mb-3.5 space-y-1.5 pl-5 list-disc text-sm leading-relaxed text-ink sm:text-base last:mb-0 marker:text-ink-secondary">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3.5 space-y-1.5 pl-5 list-decimal text-sm leading-relaxed text-ink sm:text-base last:mb-0 marker:text-ink-secondary font-sans">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="pl-1 break-words">
              {children}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="font-extrabold text-ink">
              {children}
            </strong>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-3.5 rounded-r-xl border-l-4 border-line-strong bg-surface-nested py-2 pl-4 pr-3 text-sm text-ink-secondary italic">
              {children}
            </blockquote>
          ),
          pre: ({ children }) => (
            <pre className="my-4 max-w-full overflow-x-auto rounded-xl border border-charcoal-pressed bg-primary p-4 font-mono text-xs leading-relaxed text-ivory shadow-inner sm:text-sm">
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || "");
            const isCodeBlock = match || String(children).includes("\n");
            if (isCodeBlock) {
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-xs text-ink break-words sm:text-sm"
                {...props}
              >
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="my-4 max-w-full overflow-x-auto rounded-xl border border-line bg-surface">
              <table className="w-full border-collapse text-left text-xs sm:text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-line-strong bg-surface-nested text-ink">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-line">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="transition-colors hover:bg-surface-hover">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 font-mono font-bold text-ink text-left uppercase text-xs tracking-wider">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-ink break-words">
              {children}
            </td>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-ink underline decoration-line-strong underline-offset-2 transition-colors hover:text-charcoal-hover hover:decoration-primary"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
