import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportMarkdownViewProps {
  content: string;
}

function stripLeadingH1(markdown: string): string {
  return markdown.replace(/^\s*#\s+[^\n]*\n?/, "").trim();
}

export default function ReportMarkdownView({ content }: ReportMarkdownViewProps) {
  const cleanedContent = stripLeadingH1(content);

  return (
    <div className="prose prose-neutral max-w-none text-neutral-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-8 mb-4 text-2xl font-black text-black border-b border-black pb-2 uppercase tracking-wide">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-8 mb-4 text-xl font-black text-black border-b border-black pb-2 uppercase tracking-wide">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-6 mb-3 text-lg font-black text-black">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="my-4 text-sm leading-7 text-neutral-800">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-6 my-4 space-y-2 text-sm leading-7 text-neutral-800">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-6 my-4 space-y-2 text-sm leading-7 text-neutral-800">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="pl-1">
              {children}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="font-bold text-black">
              {children}
            </strong>
          ),
          code: ({ children }) => (
            <code className="bg-neutral-100 px-1 py-0.5 font-mono text-xs font-semibold text-black rounded">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="my-6 overflow-x-auto border border-black/10">
              <table className="min-w-full text-left text-sm divide-y divide-black/10">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-neutral-50 text-[10px] font-black uppercase tracking-widest text-neutral-600 border-b border-black/10">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-black/10 bg-white">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="border-b border-black/10 last:border-b-0">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 font-black">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-3 text-xs leading-5">
              {children}
            </td>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-black pl-4 py-1 my-4 italic text-neutral-600">
              {children}
            </blockquote>
          ),
        }}
      >
        {cleanedContent || "No rendered report content is available."}
      </ReactMarkdown>
    </div>
  );
}
