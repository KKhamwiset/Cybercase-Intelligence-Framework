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
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (thread && !dialog.open) {
      dialog.showModal();
    } else if (!thread && dialog.open) {
      dialog.close();
    }
  }, [thread]);

  return (
    <dialog
      ref={dialogRef}
      role="alertdialog"
      aria-labelledby={thread ? "delete-chat-title" : undefined}
      aria-describedby={thread ? "delete-chat-description" : undefined}
      className="fixed inset-0 m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-[#DEDCD5] bg-white p-0 text-[#171717] shadow-2xl backdrop:bg-[#171717]/45 max-sm:inset-x-0 max-sm:bottom-0 max-sm:top-auto max-sm:mb-0 max-sm:w-full max-sm:max-w-none max-sm:rounded-b-none"
      onCancel={(event) => {
        event.preventDefault();
        if (!isDeleting) onCancel();
      }}
      onMouseDown={(event) => {
        if (event.target !== event.currentTarget || isDeleting) return;

        const bounds = event.currentTarget.getBoundingClientRect();
        const clickedOutside =
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom;
        if (clickedOutside) onCancel();
      }}
    >
      {thread && (
        <section className="p-6">
          <h2 id="delete-chat-title" className="text-lg font-extrabold">
            Delete chat?
          </h2>
          <p
            id="delete-chat-description"
            className="mt-3 text-sm leading-6 text-[#171717]/70"
          >
            &ldquo;{thread.title}&rdquo; and its messages and processing history
            will be permanently deleted.
            {thread.status === "processing" &&
              " The pending result will be discarded, although upstream processing may finish in the background."}
          </p>
          <div className="mt-6 flex justify-end gap-3 max-sm:flex-col-reverse">
            <button
              autoFocus
              type="button"
              disabled={isDeleting}
              onClick={onCancel}
              className="min-h-11 rounded-xl border border-[#DEDCD5] px-4 text-sm font-bold outline-none transition-colors duration-150 hover:bg-[#F7F6F2] focus-visible:ring-2 focus-visible:ring-[#171717] disabled:cursor-wait disabled:opacity-45 motion-reduce:transition-none"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isDeleting}
              onClick={onConfirm}
              className="min-h-11 rounded-xl bg-[#B42318] px-4 text-sm font-bold text-white outline-none transition-opacity duration-150 hover:opacity-85 focus-visible:ring-2 focus-visible:ring-[#B42318] focus-visible:ring-offset-2 disabled:cursor-wait disabled:opacity-45 motion-reduce:transition-none"
            >
              {isDeleting ? "Deleting\u2026" : "Delete"}
            </button>
          </div>
        </section>
      )}
    </dialog>
  );
}
