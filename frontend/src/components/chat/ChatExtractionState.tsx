import type { ChatBaselineExtractionFailure } from "@/lib/api";
import { Icon } from "./icons";

interface ChatExtractionStateProps {
  onOpenChat: () => void;
}

function ReturnToChatButton({ onOpenChat }: ChatExtractionStateProps) {
  return (
    <button
      type="button"
      onClick={onOpenChat}
      className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-[#171717] px-4 text-sm font-bold text-white outline-none transition-colors hover:bg-[#333333] focus-visible:ring-2 focus-visible:ring-[#171717] focus-visible:ring-offset-2"
    >
      Return to Chat
    </button>
  );
}

export function NoChatExtractionState({ onOpenChat }: ChatExtractionStateProps) {
  return (
    <div className="max-w-2xl rounded-2xl border border-dashed border-[#C9C7BF] bg-[#FCFBF8] p-6 sm:p-8">
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#171717] text-white shadow-sm">
        <Icon name="evidence" className="h-6 w-6" />
      </span>
      <h2 className="mt-5 text-xl font-extrabold tracking-tight text-[#171717]">
        No extraction for this chat yet
      </h2>
      <p className="mt-3 text-sm leading-6 text-[#6B6A66]">
        Send a message and wait for a terminal assistant response before
        reviewing reported case-information candidates here.
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
      aria-label="Reported case-information extraction failed"
      className="max-w-3xl rounded-2xl border border-[#E2B8B3] bg-[#FFF7F5] p-5 sm:p-6"
    >
      <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#8B1E17]">
        Schema-validated candidate extraction
      </p>
      <h2 className="mt-2 text-xl font-extrabold tracking-tight text-[#171717]">
        Extraction failed
      </h2>
      <p className="mt-3 text-sm font-bold text-[#8B1E17]">
        Failure code: {extraction.failure_code}
      </p>
      <p className="mt-2 text-sm leading-6 text-[#6B6A66]">
        {extraction.failure_message}
      </p>
      <p className="mt-2 text-xs leading-5 text-[#6B6A66]">
        The terminal assistant answer was preserved. No fallback candidate is
        shown on this reported case-information route.
      </p>
      <ReturnToChatButton onOpenChat={onOpenChat} />
    </section>
  );
}

export function LegacyRelationshipsUnavailableState({
  onOpenChat,
}: ChatExtractionStateProps) {
  return (
    <section className="max-w-3xl rounded-2xl border border-dashed border-[#C9C7BF] bg-[#FCFBF8] p-6 sm:p-8">
      <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-[#6B6A66]">
        Legacy deterministic extraction
      </p>
      <h2 className="mt-2 text-xl font-extrabold tracking-tight text-[#171717]">
        Relationship graph unavailable
      </h2>
      <p className="mt-3 text-sm leading-6 text-[#6B6A66]">
        This saved extraction predates typed entity relationships. Its reported
        case information and timeline remain available, but no relationship graph can be derived
        without inventing connections.
      </p>
      <ReturnToChatButton onOpenChat={onOpenChat} />
    </section>
  );
}
