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
      <div className="relative rounded-3xl border border-line-strong bg-surface p-3.5 shadow-[0_2px_12px_rgba(39,39,39,0.06)] transition-all focus-within:border-charcoal focus-within:ring-1 focus-within:ring-charcoal">
        <label htmlFor="chat-composer-input" className="sr-only">
          Chat message
        </label>
        <textarea
          ref={textareaRef}
          id="chat-composer-input"
          rows={2}
          value={input}
          disabled={isSubmitting}
          onKeyDown={handleKeyDown}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Describe an incident, paste forensic logs, or ask about MITRE techniques..."
          className="w-full resize-none border-none bg-transparent px-1 pt-0.5 text-sm text-ink outline-none shadow-none placeholder:text-ink-muted focus:border-none focus:outline-none focus:ring-0 focus-visible:border-none focus-visible:outline-none focus-visible:ring-0 disabled:text-ink-disabled"
        />

        <div className="mt-2 flex items-center justify-between border-t border-line/60 pt-2">
          <p className="text-[11px] text-ink-secondary">
            Press <kbd className="rounded bg-surface-nested px-1.5 py-0.5 font-mono text-[10px] text-ink-secondary">Ctrl+Enter</kbd> to submit
          </p>
          <button
            type="submit"
            disabled={isSubmitting || !input.trim()}
            aria-label="Send message"
            className="flex h-8 w-8 items-center justify-center rounded-full bg-charcoal text-ivory outline-none transition-all hover:scale-105 hover:bg-charcoal-hover active:scale-95 active:bg-charcoal-pressed focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-control-disabled disabled:text-ink-disabled disabled:hover:scale-100"
          >
            <Icon name="send" className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </form>
  );
}
