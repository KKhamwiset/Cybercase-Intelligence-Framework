"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  createChatMessage,
  createChatThread,
  deleteChatThread,
  getApiErrorMessage,
  getChatRun,
  getChatThread,
  listChatThreads,
  updateChatThread,
  type PersistedChatMessage,
  type ChatThreadDetail,
  type ChatThreadRead,
  type ThreadStatus,
} from "@/lib/api";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { DeleteChatDialog } from "@/components/chat/DeleteChatDialog";
import { Icon } from "@/components/chat/icons";
import { WorkspaceSidebar } from "@/components/chat/WorkspaceSidebar";
import type { RunPhase } from "@/components/chat/types";
import {
  activeChatFollowUpForThread,
  chatTranscriptMessages,
  hasCompletedAssistantOutput,
  persistedRequestOrdinal,
  type ActiveChatFollowUp,
} from "@/lib/chat-followup";

const POLL_INTERVAL_MS = 1000;

interface PendingSubmission {
  threadId: string;
  content: string;
  key: string;
  kind: "message" | "followup";
  lastKnownMessageOrdinal: number;
  requestOrdinal?: number;
}

const phaseLabels: Record<RunPhase, string> = {
  idle: "Ready",
  querying: "Processing",
  awaiting_followup: "Follow-up required",
  analyzing: "Validating",
  ready: "Complete",
  error: "Error",
};

function phaseForThread(detail: ChatThreadDetail): RunPhase {
  if (detail.status === "processing") return "querying";
  if (detail.status === "awaiting_followup") return "awaiting_followup";
  if (detail.status === "failed") return "error";
  return detail.messages.length > 0 ? "ready" : "idle";
}

function titleFromMessage(content: string): string {
  const normalized = content.replace(/\s+/g, " ").trim();
  if (normalized.length <= 60) return normalized;
  return `${normalized.slice(0, 57).trimEnd()}...`;
}

function waitForNextPoll(signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }

    const timeoutId = window.setTimeout(resolve, POLL_INTERVAL_MS);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeoutId);
        resolve();
      },
      { once: true },
    );
  });
}

function isCanceled(signal: AbortSignal, error: unknown): boolean {
  return (
    signal.aborted ||
    (typeof error === "object" &&
      error !== null &&
      "code" in error &&
      error.code === "ERR_CANCELED")
  );
}

export default function ChatPage() {
  const [threads, setThreads] = useState<ChatThreadRead[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [threadStatus, setThreadStatus] = useState<ThreadStatus | null>(null);
  const [messages, setMessages] = useState<PersistedChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [followUpAnswer, setFollowUpAnswer] = useState("");
  const [pendingFollowUp, setPendingFollowUp] = useState<{
    threadId: string;
    followUp: ActiveChatFollowUp;
  } | null>(null);
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [queryError, setQueryError] = useState<string | null>(null);
  const [threadsError, setThreadsError] = useState<string | null>(null);
  const [threadsLoading, setThreadsLoading] = useState(true);
  const [creatingThread, setCreatingThread] = useState(false);
  const [deleteCandidate, setDeleteCandidate] = useState<ChatThreadRead | null>(
    null,
  );
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null);

  const activeThreadIdRef = useRef<string | null>(null);
  const selectionGenerationRef = useRef(0);
  const pollControllerRef = useRef<AbortController | null>(null);
  const deletedThreadIdsRef = useRef(new Set<string>());
  const pendingSubmissionRef = useRef<PendingSubmission | null>(null);

  const upsertThread = useCallback((thread: ChatThreadRead) => {
    if (deletedThreadIdsRef.current.has(thread.id)) return;
    setThreads((current) => {
      const next = [thread, ...current.filter((item) => item.id !== thread.id)];
      return next.sort(
        (left, right) =>
          Date.parse(right.updated_at) - Date.parse(left.updated_at),
      );
    });
  }, []);

  const isCurrentSelection = useCallback(
    (threadId: string, generation: number) =>
      activeThreadIdRef.current === threadId &&
      selectionGenerationRef.current === generation,
    [],
  );

  const applyThreadDetail = useCallback(
    (detail: ChatThreadDetail, failureMessage?: string | null) => {
      const orderedMessages = [...detail.messages].sort(
        (left, right) => left.ordinal - right.ordinal,
      );
      setMessages(orderedMessages);
      setThreadStatus(detail.status);
      setPhase(phaseForThread(detail));
      upsertThread(detail);

      const pending = pendingSubmissionRef.current;
      const recoveredRequestOrdinal =
        pending?.threadId === detail.id && pending.requestOrdinal === undefined
          ? persistedRequestOrdinal(
              detail,
              pending.lastKnownMessageOrdinal,
              pending.content,
            )
          : undefined;
      if (
        pending?.threadId === detail.id &&
        recoveredRequestOrdinal !== undefined
      ) {
        pendingSubmissionRef.current = {
          ...pending,
          requestOrdinal: recoveredRequestOrdinal,
        };
      }
      const requestOrdinal =
        pending?.threadId === detail.id
          ? pending.requestOrdinal ?? recoveredRequestOrdinal
          : undefined;

      if (failureMessage || detail.status === "failed") {
        setQueryError(
          failureMessage ||
            "Background processing failed. Retry the saved message.",
        );
      } else if (
        pending?.threadId !== detail.id ||
        requestOrdinal !== undefined
      ) {
        setQueryError(null);
      }

      if (
        pending?.threadId === detail.id &&
        requestOrdinal !== undefined &&
        hasCompletedAssistantOutput(detail, requestOrdinal)
      ) {
        pendingSubmissionRef.current = null;
        setPendingFollowUp(null);
        setInput("");
        setFollowUpAnswer("");
      }
    },
    [upsertThread],
  );

  const pollThreadUntilSettled = useCallback(
    async (
      threadId: string,
      generation: number,
      signal: AbortSignal,
    ): Promise<void> => {
      let consecutiveReadFailures = 0;

      while (!signal.aborted && isCurrentSelection(threadId, generation)) {
        await waitForNextPoll(signal);
        if (signal.aborted || !isCurrentSelection(threadId, generation)) return;

        let detail: ChatThreadDetail;
        try {
          detail = await getChatThread(threadId, signal);
          consecutiveReadFailures = 0;
        } catch (error) {
          if (
            isCanceled(signal, error) ||
            !isCurrentSelection(threadId, generation)
          ) {
            return;
          }

          consecutiveReadFailures += 1;
          if (consecutiveReadFailures > 1) throw error;
          continue;
        }

        if (!isCurrentSelection(threadId, generation)) return;
        applyThreadDetail(detail);
        if (detail.status !== "processing") return;
      }
    },
    [applyThreadDetail, isCurrentSelection],
  );

  const loadThread = useCallback(
    async (
      threadId: string,
      generation: number,
      signal: AbortSignal,
    ): Promise<void> => {
      try {
        const detail = await getChatThread(threadId, signal);
        if (!isCurrentSelection(threadId, generation)) return;
        applyThreadDetail(detail);

        if (detail.status === "processing") {
          await pollThreadUntilSettled(threadId, generation, signal);
        }
      } catch (error) {
        if (isCanceled(signal, error) || !isCurrentSelection(threadId, generation)) {
          return;
        }
        setPhase("error");
        setQueryError(getApiErrorMessage(error, "The chat could not be loaded."));
      }
    },
    [applyThreadDetail, isCurrentSelection, pollThreadUntilSettled],
  );

  const selectThread = useCallback(
    async (threadId: string): Promise<void> => {
      pollControllerRef.current?.abort();
      const controller = new AbortController();
      pollControllerRef.current = controller;
      const generation = selectionGenerationRef.current + 1;
      selectionGenerationRef.current = generation;
      activeThreadIdRef.current = threadId;

      setActiveThreadId(threadId);
      setInput("");
      const pending = pendingSubmissionRef.current;
      setFollowUpAnswer(
        pending?.threadId === threadId && pending.kind === "followup"
          ? pending.content
          : "",
      );
      setPendingFollowUp((current) =>
        current?.threadId === threadId ? current : null,
      );
      setMessages([]);
      setThreadStatus(null);
      setQueryError((current) =>
        pending?.threadId === threadId ? current : null,
      );
      setPhase("querying");

      await loadThread(threadId, generation, controller.signal);
    },
    [loadThread],
  );

  useEffect(() => {
    const controller = new AbortController();

    void (async () => {
      setThreadsLoading(true);
      setThreadsError(null);
      try {
        const loadedThreads = await listChatThreads(controller.signal);
        if (controller.signal.aborted) return;
        setThreads(loadedThreads);
        if (loadedThreads[0] && activeThreadIdRef.current === null) {
          void selectThread(loadedThreads[0].id);
        }
      } catch (error) {
        if (isCanceled(controller.signal, error)) return;
        setThreadsError(
          getApiErrorMessage(error, "Saved chats could not be loaded."),
        );
      } finally {
        if (!controller.signal.aborted) setThreadsLoading(false);
      }
    })();

    return () => {
      controller.abort();
      pollControllerRef.current?.abort();
    };
  }, [selectThread]);

  const handleNewChat = useCallback(async () => {
    if (creatingThread) return;
    setCreatingThread(true);
    setThreadsError(null);
    try {
      const thread = await createChatThread();
      upsertThread(thread);
      await selectThread(thread.id);
    } catch (error) {
      setThreadsError(getApiErrorMessage(error, "A new chat could not be created."));
    } finally {
      setCreatingThread(false);
    }
  }, [creatingThread, selectThread, upsertThread]);

  const pollKnownRun = useCallback(
    async (
      threadId: string,
      runId: string,
      generation: number,
      signal: AbortSignal,
    ): Promise<ChatThreadDetail | null> => {
      let consecutiveReadFailures = 0;

      while (!signal.aborted && isCurrentSelection(threadId, generation)) {
        await waitForNextPoll(signal);
        if (signal.aborted || !isCurrentSelection(threadId, generation)) {
          return null;
        }

        let detail: ChatThreadDetail;
        try {
          detail = await getChatThread(threadId, signal);
          consecutiveReadFailures = 0;
        } catch (error) {
          if (
            isCanceled(signal, error) ||
            !isCurrentSelection(threadId, generation)
          ) {
            return null;
          }

          consecutiveReadFailures += 1;
          if (consecutiveReadFailures > 1) throw error;
          continue;
        }

        if (!isCurrentSelection(threadId, generation)) return null;

        if (detail.status === "processing") {
          applyThreadDetail(detail);
          continue;
        }

        let run;
        try {
          run = await getChatRun(threadId, runId, signal);
        } catch (error) {
          if (
            isCanceled(signal, error) ||
            !isCurrentSelection(threadId, generation)
          ) {
            return null;
          }
          throw error;
        }

        if (!isCurrentSelection(threadId, generation)) return null;
        if (run.status === "failed") {
          applyThreadDetail(
            detail,
            run.error_message || "Background processing failed. Retry the answer.",
          );
          return null;
        }
        if (run.status === "completed") {
          applyThreadDetail(detail);
          return detail;
        }
      }
      return null;
    },
    [applyThreadDetail, isCurrentSelection],
  );

  const submitContent = (
    rawContent: string,
    kind: PendingSubmission["kind"],
    followUp?: ActiveChatFollowUp,
  ) => {
    if (phase === "querying" || phase === "analyzing") return;

    const content = rawContent.trim();
    if (!content) return;
    const statusBeforeSubmit = threadStatus;

    void (async () => {
      let threadId = activeThreadIdRef.current;
      let currentThread = threads.find((thread) => thread.id === threadId);
      if (!threadId) {
        try {
          const created = await createChatThread();
          upsertThread(created);
          await selectThread(created.id);
          threadId = created.id;
          currentThread = created;
        } catch (error) {
          setQueryError(
            getApiErrorMessage(error, "A chat could not be created."),
          );
          setPhase("error");
          return;
        }
      }
      if (kind === "followup" && !followUp) return;

      const generation = selectionGenerationRef.current;
      const controller = pollControllerRef.current;
      if (!controller || !isCurrentSelection(threadId, generation)) return;

      const existingMessages = messages;
      const pending = pendingSubmissionRef.current;
      const idempotencyKey =
        pending?.threadId === threadId && pending.content === content
          ? pending.key
          : window.crypto.randomUUID();
      const lastKnownMessageOrdinal =
        pending?.threadId === threadId && pending.content === content
          ? pending.lastKnownMessageOrdinal
          : existingMessages.reduce(
              (latestOrdinal, message) =>
                Math.max(latestOrdinal, message.ordinal),
              0,
            );
      pendingSubmissionRef.current = {
        threadId,
        content,
        key: idempotencyKey,
        kind,
        lastKnownMessageOrdinal,
      };
      if (kind === "followup" && followUp) {
        setPendingFollowUp({ threadId, followUp });
      }

      setPhase("querying");
      setThreadStatus("processing");
      setQueryError(null);

      let requestAccepted = false;
      try {
        const accepted = await createChatMessage(
          threadId,
          content,
          idempotencyKey,
          controller.signal,
        );
        if (!isCurrentSelection(threadId, generation)) return;
        requestAccepted = true;
        const pendingAfterAccept = pendingSubmissionRef.current;
        if (
          pendingAfterAccept?.threadId === threadId &&
          pendingAfterAccept.key === idempotencyKey
        ) {
          pendingSubmissionRef.current = {
            ...pendingAfterAccept,
            requestOrdinal: accepted.message.ordinal,
          };
        }

        setMessages((current) => {
          if (current.some((message) => message.id === accepted.message.id)) {
            return current;
          }
          return [...current, accepted.message].sort(
            (left, right) => left.ordinal - right.ordinal,
          );
        });

        if (currentThread) {
          upsertThread({ ...currentThread, status: "processing" });
        }

        if (
          kind === "message" &&
          currentThread?.title === "New chat" &&
          existingMessages.length === 0
        ) {
          void updateChatThread(
            threadId,
            titleFromMessage(content),
            controller.signal,
          )
            .then((updated) => {
              if (isCurrentSelection(threadId, generation)) upsertThread(updated);
            })
            .catch(() => undefined);
        }

        const completedDetail = await pollKnownRun(
          threadId,
          accepted.run.id,
          generation,
          controller.signal,
        );
        if (
          completedDetail &&
          hasCompletedAssistantOutput(
            completedDetail,
            accepted.message.ordinal,
          )
        ) {
          pendingSubmissionRef.current = null;
          setPendingFollowUp(null);
          setInput("");
          setFollowUpAnswer("");
        } else if (
          completedDetail &&
          isCurrentSelection(threadId, generation)
        ) {
          setQueryError(
            "The completed run did not persist an assistant response. Retry the saved answer.",
          );
        }
      } catch (error) {
        if (
          isCanceled(controller.signal, error) ||
          !isCurrentSelection(threadId, generation)
        ) {
          return;
        }

        if (kind === "followup") {
          setThreadStatus("awaiting_followup");
          setPhase("awaiting_followup");
        } else {
          setThreadStatus(statusBeforeSubmit);
          setPhase("error");
        }
        setQueryError(
          getApiErrorMessage(
            error,
            requestAccepted
              ? "The run status could not be confirmed. Retry the saved message."
              : "The message could not be submitted.",
          ),
        );
      }
    })();
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitContent(input, "message");
  };

  const handleCancelDelete = useCallback(() => {
    if (deletingThreadId === null) setDeleteCandidate(null);
  }, [deletingThreadId]);

  const handleConfirmDelete = useCallback(async () => {
    const thread = deleteCandidate;
    if (!thread || deletingThreadId !== null) return;

    const deletingActiveThread = activeThreadIdRef.current === thread.id;
    deletedThreadIdsRef.current.add(thread.id);
    setDeletingThreadId(thread.id);
    setThreadsError(null);

    if (deletingActiveThread) {
      pollControllerRef.current?.abort();
      pollControllerRef.current = null;
      selectionGenerationRef.current += 1;
      activeThreadIdRef.current = null;
      if (pendingSubmissionRef.current?.threadId === thread.id) {
        pendingSubmissionRef.current = null;
        setPendingFollowUp(null);
      }
    }

    try {
      await deleteChatThread(thread.id);
    } catch (error) {
      deletedThreadIdsRef.current.delete(thread.id);
      setDeleteCandidate(null);
      setDeletingThreadId(null);
      setThreadsError(getApiErrorMessage(error, "The chat could not be deleted."));
      if (deletingActiveThread) await selectThread(thread.id);
      return;
    }

    const remainingThreads = threads.filter((item) => item.id !== thread.id);
    setThreads((current) => current.filter((item) => item.id !== thread.id));
    setDeleteCandidate(null);
    setDeletingThreadId(null);

    if (!deletingActiveThread) return;

    setActiveThreadId(null);
    setMessages([]);
    setInput("");
    setFollowUpAnswer("");
    setThreadStatus(null);
    setQueryError(null);
    setPhase("idle");

    if (remainingThreads[0]) await selectThread(remainingThreads[0].id);
  }, [
    deleteCandidate,
    deletingThreadId,
    selectThread,
    threads,
  ]);

  const activeThread =
    threads.find((thread) => thread.id === activeThreadId) ?? null;
  const persistedFollowUp = activeChatFollowUpForThread(messages, threadStatus);
  const displayFollowUp =
    persistedFollowUp ??
    (pendingFollowUp?.threadId === activeThreadId
      ? pendingFollowUp.followUp
      : null);
  const visibleMessages = chatTranscriptMessages(messages, displayFollowUp);
  return (
    <div className="flex h-dvh overflow-hidden bg-[#F7F6F2] text-[#171717]">
      <WorkspaceSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        threadsLoading={threadsLoading}
        threadsError={threadsError}
        onSelectThread={(threadId) => void selectThread(threadId)}
        onNewChat={() => void handleNewChat()}
        onRequestDelete={setDeleteCandidate}
        deletingThreadId={deletingThreadId}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex min-h-[76px] shrink-0 flex-wrap items-center gap-3 border-b border-[#DEDCD5] bg-[#F7F6F2] px-3 py-3 sm:px-5 md:min-h-[72px] md:flex-nowrap md:px-7">
          <div className="flex min-w-0 w-full items-center gap-3 md:flex-1">
            <Link
              href="/"
              aria-label="CyberCase home"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[#171717] text-sm font-extrabold text-white outline-none focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 md:hidden"
            >
              C
            </Link>
            <div className="min-w-0 flex-1">
              <p className="truncate text-base font-extrabold tracking-[-0.02em] sm:text-lg">
                {activeThread?.title ?? "New chat"}
              </p>
              <p className="mt-0.5 flex items-center gap-1.5 text-xs font-medium text-[#6B6A66]">
                <span className={`h-1.5 w-1.5 rounded-full ${phase === "error" ? "bg-[#B42318]" : phase === "querying" || phase === "analyzing" ? "bg-[#171717] motion-safe:animate-pulse" : "bg-[#8A8984]"}`} />
                {phaseLabels[phase]}
              </p>
            </div>
          </div>

          <div className="flex w-full items-center gap-2 md:hidden">
            <select
              value={activeThreadId ?? ""}
              onChange={(event) => {
                if (event.target.value) void selectThread(event.target.value);
              }}
              aria-label="Select saved chat"
              className="min-h-11 min-w-0 flex-1 rounded-xl border border-[#C9C7BF] bg-white px-3 text-sm font-semibold outline-none focus-visible:ring-2 focus-visible:ring-[#171717]"
            >
              <option value="">Select chat</option>
              {threads.map((thread) => (
                <option key={thread.id} value={thread.id}>
                  {thread.title}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => void handleNewChat()}
              disabled={creatingThread}
              aria-label="New chat"
              title="New chat"
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#C9C7BF] bg-white text-[#171717] outline-none transition-colors hover:border-[#171717] hover:bg-[#FCFBF8] focus-visible:ring-2 focus-visible:ring-[#171717] disabled:cursor-wait disabled:text-[#8A8984]"
            >
              <Icon name="plus" className="h-5 w-5" />
            </button>

            {activeThread && (
              <button
                type="button"
                onClick={() => setDeleteCandidate(activeThread)}
                disabled={deletingThreadId !== null}
                aria-label={`Delete ${activeThread.title}`}
                title={`Delete ${activeThread.title}`}
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[#C9C7BF] bg-white text-[#6B6A66] outline-none transition-colors hover:border-[#B42318] hover:bg-red-50 hover:text-[#B42318] focus-visible:ring-2 focus-visible:ring-[#B42318] disabled:cursor-wait disabled:text-[#C9C7BF]"
              >
                <Icon name="trash" className="h-5 w-5" />
              </button>
            )}
          </div>
        </header>

        <div className="flex min-h-0 flex-1 overflow-hidden bg-[#F7F6F2]">
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
            <ChatPanel
              messages={visibleMessages}
              input={input}
              followUp={displayFollowUp}
              followUpAnswer={followUpAnswer}
              threadStatus={threadStatus}
              phase={phase}
              error={queryError}
              onInputChange={setInput}
              onFollowUpAnswerChange={setFollowUpAnswer}
              onFollowUpSubmit={() =>
                submitContent(
                  followUpAnswer,
                  "followup",
                  displayFollowUp ?? undefined,
                )
              }
              onSubmit={handleSubmit}
            />
          </main>

        </div>
      </div>
      <DeleteChatDialog
        thread={deleteCandidate}
        isDeleting={deletingThreadId !== null}
        onCancel={handleCancelDelete}
        onConfirm={() => void handleConfirmDelete()}
      />
    </div>
  );
}
