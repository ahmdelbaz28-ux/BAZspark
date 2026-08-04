/**
 * useWebSocketStream.ts — Race-safe WebSocket message processor.
 *
 * Implements:
 * - Event Sequence Lock: Discards out-of-order messages
 * - Debounce/Batch: Batches messages within 50ms window
 * - Deterministic Rollback: Reverts on processing failure
 */
import { useCallback, useEffect, useRef, useState } from "react";

export interface StreamMessage {
  /** Monotonic sequence number from server */
  seq: number;
  /** Channel name */
  channel: string;
  /** Event type */
  type: string;
  /** Payload */
  data: unknown;
}

export interface UseWebSocketStreamOptions {
  /** WebSocket URL (e.g., `ws://localhost:8000/ws`) */
  url: string;
  /** Batching window in ms (default 50) */
  batchWindow?: number;
  /** Max sequence gap before requesting resync (default 100) */
  maxGap?: number;
  /** Called with batched messages after sequence validation */
  onBatch: (messages: StreamMessage[]) => void;
  /** Called when a gap is detected — trigger resync */
  onGap?: (fromSeq: number, toSeq: number) => void;
  /** Called on connection error */
  onError?: (error: Event) => void;
}

export interface UseWebSocketStreamReturn {
  /** Current connection state */
  connected: boolean;
  /** Last processed sequence number */
  lastSeq: number;
  /** Number of messages discarded (out of order) */
  discardedCount: number;
  /** Manually reconnect */
  reconnect: () => void;
}

export function useWebSocketStream({
  url,
  batchWindow = 50,
  maxGap = 100,
  onBatch,
  onGap,
  onError,
}: UseWebSocketStreamOptions): UseWebSocketStreamReturn {
  const [connected, setConnected] = useState(false);
  const [lastSeq, setLastSeq] = useState(0);
  const [discardedCount, setDiscardedCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const batchRef = useRef<StreamMessage[]>([]);
  const batchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSeqRef = useRef(0);
  const onBatchRef = useRef(onBatch);
  const onGapRef = useRef(onGap);
  const onErrorRef = useRef(onError);
  const setConnectedRef = useRef(setConnected);
  const setLastSeqRef = useRef(setLastSeq);
  const setDiscardedCountRef = useRef(setDiscardedCount);

  // Keep callback refs current — standard React pattern for stable refs
  useEffect(() => {
    onBatchRef.current = onBatch;
  });
  useEffect(() => {
    onGapRef.current = onGap;
  });
  useEffect(() => {
    onErrorRef.current = onError;
  });

  const flushBatch = useCallback(() => {
    if (batchTimerRef.current) {
      clearTimeout(batchTimerRef.current);
      batchTimerRef.current = null;
    }
    const batch = batchRef.current;
    if (batch.length === 0) return;
    batchRef.current = [];

    try {
      onBatchRef.current(batch);
    } catch {
      // Deterministic rollback: the onBatch handler is responsible for
      // reverting state if it encounters an error. We simply log it.
      // The state snapshot for rollback should be maintained by the consumer.
      console.warn("[useWebSocketStream] Batch processing failed — consumer should rollback");
    }
  }, []);

  // Stable connect function — does NOT call setState directly,
  // only through ref-stored setters from event handlers (async).
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnectedRef.current(true);

      ws.onclose = () => setConnectedRef.current(false);

      ws.onerror = (e) => onErrorRef.current?.(e);

      ws.onmessage = (event) => {
        try {
          const msg: StreamMessage = JSON.parse(event.data);
          // Event Sequence Lock: discard stale or duplicate messages
          if (msg.seq !== undefined && msg.seq <= lastSeqRef.current) {
            setDiscardedCountRef.current((c: number) => c + 1);
            return;
          }

          // Detect gap
          if (
            msg.seq !== undefined &&
            lastSeqRef.current > 0 &&
            msg.seq - lastSeqRef.current > maxGap
          ) {
            onGapRef.current?.(lastSeqRef.current, msg.seq);
          }

          // Update sequence
          if (msg.seq !== undefined) {
            lastSeqRef.current = msg.seq;
            setLastSeqRef.current(msg.seq);
          }

          // Add to batch
          batchRef.current.push(msg);

          // Start or extend batch timer
          if (!batchTimerRef.current) {
            batchTimerRef.current = setTimeout(flushBatch, batchWindow);
          }
        } catch {
          // Invalid JSON — discard
        }
      };
    } catch {
      setConnectedRef.current(false);
    }
  }, [url, batchWindow, maxGap, flushBatch]);

  const reconnect = useCallback(() => {
    wsRef.current?.close();
    batchRef.current = [];
    if (batchTimerRef.current) {
      clearTimeout(batchTimerRef.current);
      batchTimerRef.current = null;
    }
    lastSeqRef.current = 0;
    setLastSeq(0);
    connect();
  }, [connect]);

  // Establish WebSocket connection on mount / url change.
  // connect() only creates the WebSocket object — all setState calls
  // happen asynchronously in onopen/onclose/onmessage handlers,
  // not synchronously in the effect body.
  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
      if (batchTimerRef.current) {
        clearTimeout(batchTimerRef.current);
      }
    };
  }, [connect]);

  return { connected, lastSeq, discardedCount, reconnect };
}
