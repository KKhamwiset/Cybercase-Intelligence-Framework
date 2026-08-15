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
    badgeClass: "bg-surface-nested text-ink-secondary border-line",
    dotClass: "bg-ink-muted",
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
    <aside className="hidden h-full w-[195px] shrink-0 flex-col border-r border-line bg-sidebar md:flex">
      {/* Brand Header */}
      <Link
        href="/"
        aria-label="CyberCase home"
        className="mx-2 mt-2.5 flex min-h-9 items-center gap-2 rounded-lg px-2 outline-none transition-colors duration-150 hover:bg-surface focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-2 motion-reduce:transition-none"
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-charcoal text-[11px] font-black text-ivory shadow-sm">
          C
        </span>
        <span className="truncate text-xs font-bold tracking-tight text-ink">
          CyberCase
        </span>
      </Link>

      {/* New Investigation Button */}
      <div className="px-2 pt-2">
        <button
          type="button"
          onClick={onNewChat}
          className="flex min-h-8 w-full items-center justify-start gap-1.5 rounded-lg border border-line-strong bg-surface px-2.5 text-xs font-bold text-ink shadow-[0_1px_2px_rgba(39,39,39,0.03)] outline-none transition-all duration-150 hover:border-charcoal hover:bg-surface-hover active:bg-control-disabled focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-2 motion-reduce:transition-none"
        >
          <span className="flex h-4 w-4 items-center justify-center rounded bg-surface-nested text-ink">
            <Icon name="plus" className="h-3 w-3" />
          </span>
          <span>New chat</span>
        </button>
      </div>

      {/* Investigation Views Section */}
      <div className="px-2 pt-3">
        <p className="px-1.5 text-[8.5px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
          Views
        </p>
        <nav
          aria-label="Workspace views"
          role="tablist"
          className="mt-1 space-y-0.5"
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
                className={`group flex min-h-7.5 w-full items-center gap-2 rounded-md border px-2 text-left text-[11.5px] font-semibold outline-none transition-[background-color,border-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-2 motion-reduce:transition-none ${
                  selected
                    ? "border-line bg-surface font-bold text-ink shadow-[0_1px_2px_rgba(39,39,39,0.03)]"
                    : "border-transparent text-ink-secondary hover:bg-surface/70 hover:text-ink"
                }`}
              >
                <Icon
                  name={icon}
                  className={`h-3.5 w-3.5 shrink-0 transition-colors ${
                    selected
                      ? "text-ink"
                      : "text-ink-secondary group-hover:text-ink"
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
        className="min-h-0 flex-1 overflow-y-auto px-2 pt-3 pb-2"
      >
        <div className="flex items-center justify-between px-1.5">
          <p className="text-[8.5px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
            Recent chats
          </p>
          {threads.length > 0 && (
            <span className="rounded-full bg-surface-hover px-1.5 py-0.2 text-[8.5px] font-bold text-ink-secondary">
              {threads.length}
            </span>
          )}
        </div>

        {threadsLoading ? (
          <p className="mt-3 text-center text-xs text-ink-secondary" role="status">
            Loading…
          </p>
        ) : threadsError ? (
          <p className="mt-3 break-words px-1 text-xs leading-5 text-red-700 xl:px-2">
            {threadsError}
          </p>
        ) : threads.length === 0 ? (
          <p className="mt-3 px-1.5 text-xs leading-5 text-ink-secondary">
            No saved chats yet.
          </p>
        ) : (
          <div className="mt-1 space-y-0.5">
            {threads.map((thread) => {
              const selected = thread.id === activeThreadId;
              const statusInfo = threadStatusConfig[thread.status] ?? threadStatusConfig.idle;
              return (
                <div key={thread.id} className="group flex items-center gap-0.5">
                  <button
                    type="button"
                    aria-current={selected ? "page" : undefined}
                    aria-label={`${thread.title}, ${statusInfo.label}`}
                    title={thread.title}
                    onClick={() => onSelectThread(thread.id)}
                    className={`relative flex min-h-8.5 min-w-0 flex-1 flex-col justify-center rounded-md border px-2 py-1 text-left outline-none transition-[background-color,border-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-2 motion-reduce:transition-none ${
                      selected
                        ? "border-line bg-surface font-semibold text-ink shadow-[0_1px_2px_rgba(39,39,39,0.03)]"
                        : "border-transparent text-ink-secondary hover:bg-surface/70 hover:text-ink"
                    }`}
                  >
                    <span className="block truncate text-[11.5px] leading-tight text-ink">
                      {thread.title}
                    </span>
                    <div className="mt-0.5 flex items-center gap-1">
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusInfo.dotClass}`}
                      />
                      <span
                        className={`inline-block rounded px-1 text-[8px] font-bold uppercase tracking-wider border ${statusInfo.badgeClass}`}
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
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink-secondary opacity-0 outline-none transition-[opacity,background-color,color] duration-150 hover:bg-red-50 hover:text-[#B42318] focus:opacity-100 focus-visible:ring-2 focus-visible:ring-[#B42318] disabled:cursor-wait disabled:text-ink-disabled disabled:opacity-40 group-hover:opacity-100 group-focus-within:opacity-100 motion-reduce:transition-none"
                  >
                    <Icon name="trash" className="h-3 w-3" />
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
