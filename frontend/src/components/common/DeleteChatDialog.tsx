"use client";

import { useEffect, useRef } from "react";
import type { ChatThreadRead } from "@/lib/api";

interface DeleteChatDialogProps {
  thread: ChatThreadRead | null;
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteChatDialog({
  thread,
  isDeleting,
  onCancel,
  onConfirm,
}: DeleteChatDialogProps) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const element = dialogRef.current;
    if (!element) return;

    if (thread && !element.open) {
      element.showModal();
      cancelButtonRef.current?.focus();
    } else if (!thread && element.open) {
      element.close();
    }
  }, [thread]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="delete-chat-title"
      aria-describedby="delete-chat-description"
      onCancel={(event) => {
        event.preventDefault();
        if (!isDeleting) onCancel();
      }}
      className="m-auto max-w-md rounded-2xl border border-line bg-surface p-6 text-ink shadow-[0_20px_50px_rgba(39,39,39,0.18)] backdrop:bg-primary/35 backdrop:backdrop-blur-[1px]"
    >
      <h2 id="delete-chat-title" className="text-lg font-extrabold tracking-tight">
        Delete this chat?
      </h2>
      <p
        id="delete-chat-description"
        className="mt-3 text-sm leading-6 text-ink-secondary"
      >
        This will permanently remove{" "}
        <span className="font-bold text-ink">
          {thread?.title ?? "this chat"}
        </span>
        , its message history, and any saved extractions. This action cannot be
        undone.
      </p>
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <button
          ref={cancelButtonRef}
          type="button"
          disabled={isDeleting}
          onClick={onCancel}
          className="inline-flex min-h-10 items-center justify-center rounded-xl border border-line-strong bg-surface px-4 text-sm font-bold text-ink outline-none transition-colors hover:border-primary hover:bg-surface-hover active:bg-control-disabled focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-control-disabled disabled:text-ink-disabled"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isDeleting}
          onClick={onConfirm}
          className="inline-flex min-h-10 items-center justify-center rounded-xl bg-[#B42318] px-4 text-sm font-bold text-ivory outline-none transition-colors hover:bg-[#912018] focus-visible:ring-2 focus-visible:ring-[#B42318] focus-visible:ring-offset-2 disabled:cursor-wait disabled:bg-[#FECDCA] disabled:text-ink-disabled"
        >
          {isDeleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </dialog>
  );
}
