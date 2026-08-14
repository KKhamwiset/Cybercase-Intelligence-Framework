"use client";

import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react";
import { Icon } from "@/components/common/icons";

interface ChatComposerProps {
  input: string;
  isSubmitting: boolean;
  onInputChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function ChatComposer({
  input,
  isSubmitting,
  onInputChange,
  onSubmit,
}: ChatComposerProps) {
  const formRef = useRef<HTMLFormElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [input]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  };

  return (
    <form ref={formRef} onSubmit={onSubmit} className="relative w-full">
      <div className="relative rounded-2xl border border-[#C9C7BF] bg-white p-3 shadow-[0_2px_8px_rgba(23,23,23,0.04)] focus-within:border-[#171717] focus-within:ring-1 focus-within:ring-[#171717]">
        <label htmlFor="chat-composer-input" className="sr-only">
          Chat message
        </label>
        <textarea
          ref={textareaRef}
          id="chat-composer-input"
          rows={3}
          value={input}
          disabled={isSubmitting}
          onKeyDown={handleKeyDown}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Describe an incident, paste forensic logs, or ask about MITRE techniques..."
          className="w-full resize-none bg-transparent pr-12 text-sm text-[#171717] outline-none placeholder:text-[#8A8984] disabled:text-[#8A8984]"
        />

        <div className="mt-2 flex items-center justify-between border-t border-[#F4F3EF] pt-2">
          <p className="text-[11px] text-[#8A8984]">
            Press <kbd className="rounded bg-[#F4F3EF] px-1 font-mono text-[10px]">Ctrl+Enter</kbd> to submit
          </p>
          <button
            type="submit"
            disabled={isSubmitting || !input.trim()}
            aria-label="Send message"
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#171717] text-white outline-none transition-colors hover:bg-[#333333] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-[#DEDCD5]"
          >
            <Icon name="send" className="h-4 w-4" />
          </button>
        </div>
      </div>
    </form>
  );
}
