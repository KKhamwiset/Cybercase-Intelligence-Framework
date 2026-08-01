"use client";

import Link from "next/link";
import type { ChatThreadRead } from "@/lib/api";
import { Icon } from "./icons";

interface WorkspaceNavigationProps {
  threads: ChatThreadRead[];
  activeThreadId: string | null;
  threadsLoading: boolean;
  threadsError: string | null;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onRequestDelete: (thread: ChatThreadRead) => void;
  deletingThreadId: string | null;
}

const threadStatusLabels: Record<ChatThreadRead["status"], string> = {
  idle: "Ready",
  processing: "Processing",
  awaiting_followup: "Follow-up",
  failed: "Failed",
};

export function WorkspaceSidebar({
  threads,
  activeThreadId,
  threadsLoading,
  threadsError,
  onSelectThread,
  onNewChat,
  onRequestDelete,
  deletingThreadId,
}: WorkspaceNavigationProps) {
  return (
    <aside className="hidden h-full w-[272px] shrink-0 flex-col border-r border-[#DEDCD5] bg-[#F4F3EF] md:flex">
      <Link
        href="/"
        aria-label="CyberCase home"
        className="mx-4 mt-4 flex min-h-12 items-center gap-3 rounded-xl px-3 outline-none transition-colors duration-150 hover:bg-white focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[#171717] text-sm font-extrabold text-white shadow-sm">
          C
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-extrabold tracking-tight">
            CyberCase
          </span>
          <span className="block text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">
            Chat workspace
          </span>
        </span>
      </Link>

      <div className="px-4 pt-5">
        <button
          type="button"
          onClick={onNewChat}
          className="flex min-h-11 w-full items-center justify-start gap-2 rounded-xl border border-[#C9C7BF] bg-white px-3 text-sm font-bold text-[#171717] shadow-[0_1px_2px_rgba(23,23,23,0.05)] outline-none transition-[border-color,background-color,box-shadow] duration-150 hover:border-[#171717] hover:bg-[#FCFBF8] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none"
        >
          <Icon name="plus" className="h-5 w-5" />
          <span>New chat</span>
        </button>
      </div>

      <section
        aria-label="Saved chats"
        className="min-h-0 flex-1 overflow-y-auto px-4 py-5"
      >
        <p className="px-2 text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
          Recent chats
        </p>
        {threadsLoading ? (
          <p className="mt-3 text-center text-xs text-gray-500" role="status">
            Loading…
          </p>
        ) : threadsError ? (
          <p className="mt-3 break-words px-1 text-xs leading-5 text-red-700 xl:px-2">
            {threadsError}
          </p>
        ) : threads.length === 0 ? (
          <p className="mt-3 px-2 text-xs leading-5 text-[#6B6A66]">
            No saved chats yet.
          </p>
        ) : (
          <div className="mt-2 space-y-1">
            {threads.map((thread) => {
              const selected = thread.id === activeThreadId;
              return (
                <div key={thread.id} className="group flex items-center gap-1">
                  <button
                    type="button"
                    aria-current={selected ? "page" : undefined}
                    aria-label={`${thread.title}, ${threadStatusLabels[thread.status]}`}
                    title={thread.title}
                    onClick={() => onSelectThread(thread.id)}
                    className={`flex min-h-11 min-w-0 flex-1 items-center gap-2 rounded-xl border px-2.5 text-left outline-none transition-[background-color,border-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none ${
                      selected
                        ? "border-[#DEDCD5] bg-white text-[#171717] shadow-[0_1px_2px_rgba(23,23,23,0.04)]"
                        : "border-transparent text-[#6B6A66] hover:bg-white/70 hover:text-[#171717]"
                    }`}
                  >
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      thread.status === "failed"
                        ? "bg-red-600"
                        : thread.status === "processing"
                          ? "animate-pulse bg-black motion-reduce:animate-none"
                          : thread.status === "awaiting_followup"
                            ? "border border-black bg-white"
                            : "bg-gray-400"
                    }`}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-bold">
                      {thread.title}
                    </span>
                    <span className="block text-[10px] font-semibold text-gray-500">
                      {threadStatusLabels[thread.status]}
                    </span>
                  </span>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${thread.title}`}
                    title={`Delete ${thread.title}`}
                    disabled={deletingThreadId !== null}
                    onClick={() => onRequestDelete(thread)}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[#6B6A66] opacity-0 outline-none transition-[opacity,background-color,color] duration-150 hover:bg-red-50 hover:text-[#B42318] focus:opacity-100 focus-visible:ring-2 focus-visible:ring-[#B42318] disabled:cursor-wait disabled:opacity-40 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none"
                  >
                    <Icon name="trash" className="h-4 w-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

    </aside>
  );
}
