"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ChatMessageMarkdownProps {
  content: string;
}

export function ChatMessageMarkdown({ content }: ChatMessageMarkdownProps) {
  return (
    <div className="markdown-content text-sm leading-6 text-[#171717] sm:text-base sm:leading-7">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-4 mb-2 text-xl font-extrabold tracking-tight text-[#171717] sm:text-2xl first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-4 mb-2 text-lg font-bold tracking-tight text-[#171717] sm:text-xl first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-3 mb-1.5 text-base font-bold text-[#171717] sm:text-lg first:mt-0">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-3 mb-1 text-sm font-bold text-[#171717] sm:text-base first:mt-0">
              {children}
            </h4>
          ),
          h5: ({ children }) => (
            <h5 className="mt-2 mb-1 text-sm font-bold text-[#171717] first:mt-0">
              {children}
            </h5>
          ),
          h6: ({ children }) => (
            <h6 className="mt-2 mb-1 text-xs font-bold uppercase tracking-wider text-[#6B6A66] first:mt-0">
              {children}
            </h6>
          ),
          p: ({ children }) => (
            <p className="mb-3 text-sm leading-6 text-[#171717] break-words sm:text-base sm:leading-7 last:mb-0">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="mb-3 space-y-1 pl-5 list-disc text-sm leading-6 text-[#171717] sm:text-base sm:leading-7 last:mb-0">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-3 space-y-1 pl-5 list-decimal text-sm leading-6 text-[#171717] sm:text-base sm:leading-7 last:mb-0">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="pl-1 break-words">
              {children}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="font-extrabold text-[#171717]">
              {children}
            </strong>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-3 rounded-r-md border-l-4 border-[#171717] bg-[#E8E8E5]/40 py-1.5 pl-4 pr-3 text-sm italic text-[#6B6A66]">
              {children}
            </blockquote>
          ),
          pre: ({ children }) => (
            <pre className="my-3 max-w-full overflow-x-auto rounded-lg bg-[#171717] p-3.5 font-mono text-xs text-white sm:p-4 sm:text-sm leading-relaxed">
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
                className="rounded bg-[#E8E8E5] px-1.5 py-0.5 font-mono text-xs text-[#171717] break-words sm:text-sm"
                {...props}
              >
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="my-4 max-w-full overflow-x-auto rounded-lg border border-[#DEDCD5]">
              <table className="w-full border-collapse text-left text-xs sm:text-sm">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-[#DEDCD5] bg-[#E8E8E5]/70">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-[#DEDCD5]">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="transition-colors hover:bg-black/5">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-3.5 py-2.5 font-extrabold text-[#171717] text-left">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3.5 py-2.5 text-[#171717] break-words">
              {children}
            </td>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-[#171717] underline decoration-[#171717]/40 underline-offset-2 hover:decoration-[#171717]"
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
