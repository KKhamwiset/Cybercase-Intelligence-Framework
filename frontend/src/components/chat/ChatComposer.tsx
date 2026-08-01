"use client";

import type { FormEvent, KeyboardEvent } from "react";
import { Icon } from "./icons";

interface ChatComposerProps {
  input: string;
  isAwaitingFollowUp: boolean;
  isBusy: boolean;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ChatComposer({
  input,
  isAwaitingFollowUp,
  isBusy,
  onInputChange,
  onSubmit,
}: ChatComposerProps) {
  const canSubmit = !isBusy && Boolean(input.trim());

  const handleComposerKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  return (
    <footer className="shrink-0 border-t border-[#DEDCD5] bg-[#F7F6F2]/95 px-3 pb-[max(12px,env(safe-area-inset-bottom))] pt-3 sm:px-7 sm:py-4 lg:px-10">
      <form onSubmit={onSubmit} className="mx-auto max-w-[800px]">
        <div className="flex items-end gap-2 rounded-2xl border border-[#C9C7BF] bg-white p-2 shadow-[0_8px_30px_rgba(23,23,23,0.07)] transition-[border-color,box-shadow] duration-150 focus-within:border-[#171717] focus-within:shadow-[0_10px_34px_rgba(23,23,23,0.1)] focus-within:ring-2 focus-within:ring-[#171717]/10 motion-reduce:transition-none">
          <textarea
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            disabled={isBusy}
            rows={1}
            placeholder={
              isAwaitingFollowUp
                ? "Answer the assistant’s follow-up question"
                : "Ask a question or describe the incident"
            }
            aria-label="Chat message"
            className="max-h-36 min-h-11 flex-1 resize-y bg-transparent px-2 py-2.5 text-base leading-6 text-[#171717] outline-none placeholder:text-[#8A8984] disabled:cursor-wait disabled:text-[#8A8984]"
          />

          <button
            type="submit"
            disabled={!canSubmit}
            aria-label="Send message"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#171717] text-white outline-none transition-[background-color,transform] duration-150 hover:bg-black active:scale-[0.97] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#DEDCD5] disabled:text-[#8A8984] motion-reduce:transform-none motion-reduce:transition-none"
          >
            <Icon name="send" className="h-5 w-5" />
          </button>
        </div>

        <p className="mt-2 px-1 text-xs leading-5 text-[#6B6A66]">
          {isAwaitingFollowUp
            ? "This answer continues the active backend-managed follow-up."
            : "Messages are saved to the selected chat after the backend accepts them."}
        </p>
      </form>
    </footer>
  );
}
