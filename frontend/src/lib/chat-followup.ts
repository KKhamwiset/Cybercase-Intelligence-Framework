import type {
  ChatThreadDetail,
  PersistedChatMessage,
  ThreadStatus,
} from "@/lib/api";

export interface ChatFollowUpEntry {
  question: string;
  answer: string;
}

export interface ActiveChatFollowUp {
  question: string;
  entries: ChatFollowUpEntry[];
  rootOrdinal: number;
}

interface FollowUpMetadata {
  rootOrdinal: number;
  round: number;
}

function followUpMetadata(
  message: PersistedChatMessage,
): FollowUpMetadata | null {
  const value = message.metadata_json.chat_followup;
  if (
    typeof value !== "object" ||
    value === null ||
    !("kind" in value) ||
    value.kind !== "clarification" ||
    !("root_ordinal" in value) ||
    typeof value.root_ordinal !== "number" ||
    !Number.isInteger(value.root_ordinal) ||
    value.root_ordinal < 1 ||
    !("round" in value) ||
    typeof value.round !== "number" ||
    !Number.isInteger(value.round) ||
    value.round < 1
  ) {
    return null;
  }

  return {
    rootOrdinal: value.root_ordinal,
    round: value.round,
  };
}

function orderedMessages(
  persistedMessages: PersistedChatMessage[],
): PersistedChatMessage[] {
  return [...persistedMessages].sort(
    (left, right) => left.ordinal - right.ordinal,
  );
}

export function latestUserAnswerBetween(
  persistedMessages: PersistedChatMessage[],
  questionOrdinal: number,
  nextAssistantOrdinal?: number,
): PersistedChatMessage | null {
  const candidates = orderedMessages(persistedMessages).filter(
    (message) =>
      message.role === "user" &&
      message.ordinal > questionOrdinal &&
      (nextAssistantOrdinal === undefined ||
        message.ordinal < nextAssistantOrdinal),
  );
  return candidates[candidates.length - 1] ?? null;
}

export function activeChatFollowUpForThread(
  persistedMessages: PersistedChatMessage[],
  status: ThreadStatus | null,
): ActiveChatFollowUp | null {
  if (status !== "awaiting_followup") return null;

  const ordered = orderedMessages(persistedMessages);
  const annotatedQuestions = ordered
    .filter((message) => message.role === "assistant")
    .map((message) => ({ message, metadata: followUpMetadata(message) }))
    .filter(
      (
        candidate,
      ): candidate is {
        message: PersistedChatMessage;
        metadata: FollowUpMetadata;
      } => candidate.metadata !== null,
    );

  const activeMessage = [...ordered]
    .reverse()
    .find((message) => message.role === "assistant");
  if (!activeMessage) return null;
  const activeMetadata = followUpMetadata(activeMessage);

  const rootOrdinal =
    activeMetadata?.rootOrdinal ??
    [...ordered]
      .reverse()
      .find(
        (message) =>
          message.role === "user" &&
          message.ordinal < activeMessage.ordinal,
      )?.ordinal;
  if (rootOrdinal === undefined) return null;

  const priorQuestions = activeMetadata
    ? annotatedQuestions.filter(
        (candidate) =>
          candidate.metadata.rootOrdinal === rootOrdinal &&
          candidate.message.ordinal < activeMessage.ordinal,
      )
    : [];
  const entries = priorQuestions.flatMap((candidate, index) => {
    const nextQuestionOrdinal =
      priorQuestions[index + 1]?.message.ordinal ?? activeMessage.ordinal;
    const answer = latestUserAnswerBetween(
      ordered,
      candidate.message.ordinal,
      nextQuestionOrdinal,
    );
    return answer
      ? [{ question: candidate.message.content, answer: answer.content }]
      : [];
  });

  return {
    question: activeMessage.content,
    entries,
    rootOrdinal,
  };
}

export function filterSupersededClarificationAnswers(
  persistedMessages: PersistedChatMessage[],
): PersistedChatMessage[] {
  const ordered = orderedMessages(persistedMessages);
  const supersededMessageIds = new Set<string>();

  for (const message of ordered) {
    if (message.role !== "assistant" || followUpMetadata(message) === null) {
      continue;
    }

    const nextAssistant = ordered.find(
      (candidate) =>
        candidate.role === "assistant" &&
        candidate.ordinal > message.ordinal,
    );
    const latestAnswer = latestUserAnswerBetween(
      ordered,
      message.ordinal,
      nextAssistant?.ordinal,
    );
    for (const candidate of ordered) {
      if (
        candidate.role === "user" &&
        candidate.ordinal > message.ordinal &&
        (nextAssistant === undefined ||
          candidate.ordinal < nextAssistant.ordinal) &&
        candidate.id !== latestAnswer?.id
      ) {
        supersededMessageIds.add(candidate.id);
      }
    }
  }

  return ordered.filter((message) => !supersededMessageIds.has(message.id));
}

export function chatTranscriptMessages(
  persistedMessages: PersistedChatMessage[],
  activeFollowUp: ActiveChatFollowUp | null,
): PersistedChatMessage[] {
  const ordered = orderedMessages(persistedMessages);
  if (activeFollowUp) {
    return ordered.filter(
      (message) => message.ordinal <= activeFollowUp.rootOrdinal,
    );
  }
  return filterSupersededClarificationAnswers(ordered);
}

export function persistedRequestOrdinal(
  detail: ChatThreadDetail,
  lastKnownMessageOrdinal: number,
  content: string,
): number | undefined {
  return orderedMessages(detail.messages).find(
    (message) =>
      message.role === "user" &&
      message.ordinal > lastKnownMessageOrdinal &&
      message.content === content,
  )?.ordinal;
}

export function hasCompletedAssistantOutput(
  detail: ChatThreadDetail,
  requestOrdinal: number,
): boolean {
  if (detail.status !== "idle" && detail.status !== "awaiting_followup") {
    return false;
  }
  return detail.messages.some(
    (message) =>
      message.role === "assistant" &&
      message.ordinal > requestOrdinal &&
      Boolean(message.content.trim()),
  );
}
