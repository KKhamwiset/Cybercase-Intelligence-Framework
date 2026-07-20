"use client";

import { Dispatch, SetStateAction, useEffect, useRef, useState } from "react";

function readDraft<T>(key: string, fallback: T): { exists: boolean; value: T } {
  if (typeof window === "undefined") {
    return { exists: false, value: fallback };
  }
  const stored = window.sessionStorage.getItem(key);
  if (stored === null) {
    return { exists: false, value: fallback };
  }
  try {
    return { exists: true, value: JSON.parse(stored) as T };
  } catch {
    return { exists: false, value: fallback };
  }
}

export function useSessionDraft<T>(key: string, initialValue: T) {
  const initialValueRef = useRef(initialValue);
  useEffect(() => {
    initialValueRef.current = initialValue;
  }, [initialValue]);

  const [state, setState] = useState<{ key: string; draft: T }>(() => {
    const stored = readDraft(key, initialValue);
    return { key, draft: stored.exists ? stored.value : initialValue };
  });

  const draft = state.key === key ? state.draft : initialValue;

  useEffect(() => {
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      if (cancelled) {
        return;
      }
      const stored = readDraft(key, initialValueRef.current);
      setState({
        key,
        draft: stored.exists ? stored.value : initialValueRef.current,
      });
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [key, initialValue]);

  const setDraft: Dispatch<SetStateAction<T>> = (value) => {
    setState((current) => {
      const stored = readDraft(key, initialValueRef.current);
      const currentDraft =
        current.key === key
          ? current.draft
          : stored.exists
            ? stored.value
            : initialValueRef.current;
      const nextDraft =
        typeof value === "function"
          ? (value as (previous: T) => T)(currentDraft)
          : value;

      if (JSON.stringify(nextDraft) === JSON.stringify(initialValueRef.current)) {
        window.sessionStorage.removeItem(key);
      } else {
        window.sessionStorage.setItem(key, JSON.stringify(nextDraft));
      }
      return { key, draft: nextDraft };
    });
  };

  const clearDraft = (nextValue: T = initialValueRef.current) => {
    window.sessionStorage.removeItem(key);
    setState({ key, draft: nextValue });
  };

  return { draft, setDraft, clearDraft };
}
