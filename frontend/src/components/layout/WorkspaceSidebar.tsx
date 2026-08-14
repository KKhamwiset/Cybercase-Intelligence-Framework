"use client";

import Link from "next/link";
import type { ChatThreadRead } from "@/lib/api";
import { Icon } from "@/components/common/icons";
import type { IconName } from "@/components/common/icons";
import {
  workspaceViewDescriptions,
  workspaceViewLabels,
  type WorkspaceView,
} from "@/components/common/types";

interface WorkspaceNavigationProps {
  threads: ChatThreadRead[];
  activeThreadId: string | null;
  threadsLoading: boolean;
  threadsError: string | null;
  onSelectThread: (threadId: string) => void;
  onNewChat: () => void;
  onRequestDelete: (thread: ChatThreadRead) => void;
  deletingThreadId: string | null;
  activeView: WorkspaceView;
  onViewChange: (view: WorkspaceView) => void;
}

const threadStatusConfig: Record<
  ChatThreadRead["status"],
  { label: string; badgeClass: string; dotClass: string }
> = {
  idle: {
    label: "Ready",
    badgeClass: "bg-[#F4F3EF] text-[#6B6A66] border-[#DEDCD5]",
    dotClass: "bg-[#8A8984]",
  },
  processing: {
    label: "Analyzing...",
    badgeClass: "bg-[#EFF8FF] text-[#175CD3] border-[#B2DDFF]",
    dotClass: "bg-[#175CD3] animate-pulse motion-reduce:animate-none",
  },
  awaiting_followup: {
    label: "Clarification",
    badgeClass: "bg-[#FFFAEB] text-[#B54708] border-[#FEDF89]",
    dotClass: "bg-[#B54708]",
  },
  answered: {
    label: "Answered",
    badgeClass: "bg-[#ECFDF3] text-[#027A48] border-[#ABEFC6]",
    dotClass: "bg-[#12B76A]",
  },
  failed: {
    label: "Failed",
    badgeClass: "bg-[#FEF3F2] text-[#B42318] border-[#FECDCA]",
    dotClass: "bg-[#F04438]",
  },
};

const workspaceTabs: Array<{ view: WorkspaceView; icon: IconName }> = [
  { view: "chat", icon: "chat" },
  { view: "extraction", icon: "details" },
  { view: "timeline", icon: "timeline" },
  { view: "relationships", icon: "relationships" },
  { view: "report", icon: "report" },
];

export function WorkspaceSidebar({
  threads,
  activeThreadId,
  threadsLoading,
  threadsError,
  onSelectThread,
  onNewChat,
  onRequestDelete,
  deletingThreadId,
  activeView,
  onViewChange,
}: WorkspaceNavigationProps) {
  return (
    <aside className="hidden h-full w-[280px] shrink-0 flex-col border-r border-[#DEDCD5] bg-[#F4F3EF] md:flex">
      {/* Brand Header */}
      <Link
        href="/"
        aria-label="CyberCase home"
        className="mx-4 mt-4 flex min-h-12 items-center gap-3 rounded-xl px-3 outline-none transition-colors duration-150 hover:bg-white focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[#171717] text-sm font-extrabold text-white shadow-sm">
          C
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-extrabold tracking-tight text-[#171717]">
            CyberCase
          </span>
          <span className="block text-[10px] font-bold uppercase tracking-[0.16em] text-[#8A8984]">
            Threat Intelligence
          </span>
        </span>
      </Link>

      {/* New Investigation Button */}
      <div className="px-4 pt-4">
        <button
          type="button"
          onClick={onNewChat}
          className="flex min-h-11 w-full items-center justify-start gap-2.5 rounded-xl border border-[#C9C7BF] bg-white px-3.5 text-sm font-bold text-[#171717] shadow-[0_1px_3px_rgba(23,23,23,0.06)] outline-none transition-all duration-150 hover:border-[#171717] hover:bg-[#FCFBF8] hover:shadow-[0_2px_5px_rgba(23,23,23,0.08)] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#F4F3EF] text-[#171717]">
            <Icon name="plus" className="h-4 w-4" />
          </span>
          <span>New chat</span>
        </button>
      </div>

      {/* Investigation Views Section */}
      <div className="px-4 pt-5">
        <p className="px-2 text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#8A8984]">
          Investigation views
        </p>
        <nav
          aria-label="Workspace views"
          role="tablist"
          className="mt-2 space-y-1"
        >
          {workspaceTabs.map(({ view, icon }) => {
            const selected = view === activeView;
            return (
              <button
                key={view}
                id={`workspace-tab-${view}`}
                type="button"
                role="tab"
                aria-selected={selected}
                aria-controls={`workspace-${view}-panel`}
                tabIndex={selected ? 0 : -1}
                title={workspaceViewDescriptions[view]}
                onClick={() => onViewChange(view)}
                className={`group flex min-h-10 w-full items-center gap-3 rounded-xl border px-3 text-left text-sm font-bold outline-none transition-[background-color,border-color,color,box-shadow] duration-150 focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none ${
                  selected
                    ? "border-[#DEDCD5] bg-white text-[#171717] shadow-[0_1px_3px_rgba(23,23,23,0.05)]"
                    : "border-transparent text-[#6B6A66] hover:bg-white/70 hover:text-[#171717]"
                }`}
              >
                <Icon
                  name={icon}
                  className={`h-4.5 w-4.5 shrink-0 transition-colors ${
                    selected
                      ? "text-[#171717]"
                      : "text-[#8A8984] group-hover:text-[#171717]"
                  }`}
                />
                <span className="truncate">{workspaceViewLabels[view]}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Recent Chats Section */}
      <section
        aria-label="Saved chats"
        className="min-h-0 flex-1 overflow-y-auto px-4 pt-5 pb-4"
      >
        <div className="flex items-center justify-between px-2">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#8A8984]">
            Recent chats
          </p>
          {threads.length > 0 && (
            <span className="rounded-full bg-[#EAE8E1] px-1.5 py-0.2 text-[10px] font-bold text-[#6B6A66]">
              {threads.length}
            </span>
          )}
        </div>

        {threadsLoading ? (
          <p className="mt-3 text-center text-xs text-gray-500" role="status">
            Loading…
          </p>
        ) : threadsError ? (
          <p className="mt-3 break-words px-1 text-xs leading-5 text-red-700 xl:px-2">
            {threadsError}
          </p>
        ) : threads.length === 0 ? (
          <p className="mt-3 px-2 text-xs leading-5 text-[#8A8984]">
            No saved chats yet.
          </p>
        ) : (
          <div className="mt-2 space-y-1">
            {threads.map((thread) => {
              const selected = thread.id === activeThreadId;
              const statusInfo = threadStatusConfig[thread.status] ?? threadStatusConfig.idle;
              return (
                <div key={thread.id} className="group flex items-center gap-1">
                  <button
                    type="button"
                    aria-current={selected ? "page" : undefined}
                    aria-label={`${thread.title}, ${statusInfo.label}`}
                    title={thread.title}
                    onClick={() => onSelectThread(thread.id)}
                    className={`relative flex min-h-12 min-w-0 flex-1 flex-col justify-center rounded-xl border px-3 py-1.5 text-left outline-none transition-[background-color,border-color,color,box-shadow] duration-150 focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 motion-reduce:transition-none ${
                      selected
                        ? "border-[#DEDCD5] bg-white text-[#171717] shadow-[0_1px_3px_rgba(23,23,23,0.05)]"
                        : "border-transparent text-[#6B6A66] hover:bg-white/70 hover:text-[#171717]"
                    }`}
                  >
                    <span className="block truncate text-xs font-bold leading-tight text-[#171717]">
                      {thread.title}
                    </span>
                    <div className="mt-1 flex items-center gap-1.5">
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusInfo.dotClass}`}
                      />
                      <span
                        className={`inline-block rounded px-1.5 py-0.2 text-[9px] font-bold uppercase tracking-wider border ${statusInfo.badgeClass}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${thread.title}`}
                    title={`Delete ${thread.title}`}
                    disabled={deletingThreadId !== null}
                    onClick={() => onRequestDelete(thread)}
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[#8A8984] opacity-0 outline-none transition-[opacity,background-color,color] duration-150 hover:bg-red-50 hover:text-[#B42318] focus:opacity-100 focus-visible:ring-2 focus-visible:ring-[#B42318] disabled:cursor-wait disabled:opacity-40 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none"
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
