import type { ChatBaselineExtractionFailure } from "@/lib/api";
import { Icon } from "@/components/common/icons";

interface ChatExtractionStateProps {
  onOpenChat: () => void;
}

function ReturnToChatButton({ onOpenChat }: ChatExtractionStateProps) {
  return (
    <button
      type="button"
      onClick={onOpenChat}
      className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-primary px-4 text-sm font-bold text-ivory outline-none transition-colors hover:bg-charcoal-hover active:bg-charcoal-pressed focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
    >
      Return to Chat
    </button>
  );
}

export function NoChatExtractionState({ onOpenChat }: ChatExtractionStateProps) {
  return (
    <div className="max-w-2xl rounded-2xl border border-dashed border-line-strong bg-surface p-6 sm:p-8">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-ivory shadow-sm">
        <Icon name="details" className="h-6 w-6" />
      </span>
      <h2 className="mt-5 text-xl font-extrabold tracking-tight text-ink">
        No extraction for this chat yet
      </h2>
      <p className="mt-3 text-sm leading-6 text-ink-secondary">
        Send a message and wait for a terminal assistant response before
        reviewing candidate extraction metadata here.
      </p>
      <ReturnToChatButton onOpenChat={onOpenChat} />
    </div>
  );
}

export function FailedChatExtractionState({
  extraction,
  onOpenChat,
}: ChatExtractionStateProps & { extraction: ChatBaselineExtractionFailure }) {
  return (
    <section
      aria-label="Extraction failed"
      className="max-w-3xl rounded-2xl border border-[#E2B8B3] bg-[#FFF7F5] p-5 sm:p-6"
    >
      <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#8B1E17]">
        Baseline LLM extraction
      </p>
      <h2 className="mt-2 text-xl font-extrabold tracking-tight text-ink">
        Extraction failed
      </h2>
      <p className="mt-3 text-sm font-bold text-[#8B1E17]">
        Failure code: {extraction.failure_code}
      </p>
      <p className="mt-2 text-sm leading-6 text-ink-secondary">
        {extraction.failure_message}
      </p>
      <p className="mt-2 text-xs leading-5 text-ink-secondary">
        The terminal assistant answer was preserved. No fallback candidate is
        shown on this case details route.
      </p>
      <ReturnToChatButton onOpenChat={onOpenChat} />
    </section>
  );
}
