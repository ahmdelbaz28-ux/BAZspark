/**
 * useDebouncedCallback.ts — Debounced callback hook.
 *
 * Ensures rapid successive calls are collapsed into a single
 * invocation after the specified delay.
 */
import { useCallback, useEffect, useRef } from "react";

export function useDebouncedCallback<T extends (...args: unknown[]) => void>(
  callback: T,
  delay: number,
): T {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbackRef = useRef(callback);

  // Keep callback ref current — this is a standard React pattern for
  // stable refs that avoids adding the callback to deps.
  useEffect(() => {
    callbackRef.current = callback;
  });

  const debounced = useCallback(
    (...args: unknown[]) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => callbackRef.current(...args), delay);
    },
    [delay],
  );

  return debounced as T;
}
