"use client";

import { Dispatch, SetStateAction, useEffect, useState } from "react";

function readDraft<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }
  const stored = window.sessionStorage.getItem(key);
  if (!stored) {
    return fallback;
  }
  try {
    return JSON.parse(stored) as T;
  } catch {
    return fallback;
  }
}

export function useSessionDraft<T>(key: string, initialValue: T) {
  const [state, setState] = useState<{ key: string; draft: T }>(() => {
    return { key, draft: readDraft(key, initialValue) };
  });
  const draft = state.key === key ? state.draft : readDraft(key, initialValue);

  useEffect(() => {
    if (JSON.stringify(draft) === JSON.stringify(initialValue)) {
      window.sessionStorage.removeItem(key);
      return;
    }
    window.sessionStorage.setItem(key, JSON.stringify(draft));
  }, [draft, initialValue, key]);

  const setDraft: Dispatch<SetStateAction<T>> = (value) => {
    setState((current) => {
      const currentDraft = current.key === key ? current.draft : readDraft(key, initialValue);
      return {
        key,
        draft:
          typeof value === "function"
            ? (value as (previous: T) => T)(currentDraft)
            : value,
      };
    });
  };

  const clearDraft = () => {
    window.sessionStorage.removeItem(key);
    setState({ key, draft: initialValue });
  };

  return { draft, setDraft, clearDraft };
}
