import { useEffect, useRef } from "react";

/** Runs `callback` every `delayMs` milliseconds. Pass `null` to pause -
 * used so the live events poll only runs while a ticket is actually running. */
export function useInterval(callback: () => void, delayMs: number | null): void {
  const savedCallback = useRef(callback);
  savedCallback.current = callback;

  useEffect(() => {
    if (delayMs === null) return;
    const id = setInterval(() => savedCallback.current(), delayMs);
    return () => clearInterval(id);
  }, [delayMs]);
}
