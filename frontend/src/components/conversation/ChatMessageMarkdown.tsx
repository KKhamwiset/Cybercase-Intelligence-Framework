"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessageMarkdownProps {
  content: string;
}

export function ChatMessageMarkdown({ content }: ChatMessageMarkdownProps) {
  return (
    <div className="markdown-content text-sm leading-relaxed text-slate-200 sm:text-base">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-5 mb-3 text-xl font-extrabold tracking-tight text-white sm:text-2xl first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-4 mb-2 text-lg font-bold tracking-tight text-white sm:text-xl first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-3.5 mb-2 text-base font-bold text-slate-100 sm:text-lg first:mt-0">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-3 mb-1.5 text-sm font-bold text-slate-200 sm:text-base first:mt-0">
              {children}
            </h4>
          ),
          h5: ({ children }) => (
            <h5 className="mt-2 mb-1 text-sm font-semibold text-slate-300 first:mt-0">
              {children}
            </h5>
          ),
          h6: ({ children }) => (
            <h6 className="mt-2 mb-1 text-xs font-mono font-bold uppercase tracking-wider text-slate-400 first:mt-0">
              {children}
            </h6>
          ),
          p: ({ children }) => (
            <p className="mb-3.5 text-sm leading-relaxed text-slate-200 break-words sm:text-base last:mb-0">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="mb-3.5 space-y-1.5 pl-5 list-disc text-sm leading-relaxed text-slate-200 sm:text-base last:mb-0 marker:text-cyan-400">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3.5 space-y-1.5 pl-5 list-decimal text-sm leading-relaxed text-slate-200 sm:text-base last:mb-0 marker:text-cyan-400 font-sans">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="pl-1 break-words">
              {children}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="font-extrabold text-white">
              {children}
            </strong>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-3.5 rounded-r-xl border-l-4 border-cyan-500 bg-cyan-950/20 py-2 pl-4 pr-3 text-sm text-slate-300 italic">
              {children}
            </blockquote>
          ),
          pre: ({ children }) => (
            <pre className="my-4 max-w-full overflow-x-auto rounded-xl bg-slate-950/90 border border-slate-800 p-4 font-mono text-xs text-cyan-300 sm:text-sm leading-relaxed shadow-inner">
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
                className="rounded bg-[#E8E8E5] dark:bg-slate-800 dark:text-cyan-300 px-1.5 py-0.5 font-mono text-xs text-[#171717] break-words sm:text-sm"
                {...props}
              >
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="my-4 max-w-full overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
              <table className="w-full border-collapse text-left text-xs sm:text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-slate-800 bg-slate-900/80 text-slate-200">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-800/80">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="transition-colors hover:bg-slate-800/40">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 font-mono font-bold text-cyan-300 text-left uppercase text-xs tracking-wider">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-slate-200 break-words">
              {children}
            </td>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-cyan-400 underline decoration-cyan-500/40 underline-offset-2 hover:text-cyan-300 hover:decoration-cyan-300 transition-colors"
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
