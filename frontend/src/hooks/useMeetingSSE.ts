"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface SSEMessage {
  type: string;
  id?: string;
  agent_id?: string;
  agent_name?: string;
  role?: string;
  content?: string;
  round_number?: number;
  round?: number;
  total_rounds?: number;
  status?: string;
  detail?: string;
}

interface UseMeetingSSEOptions {
  meetingId: string;
  enabled: boolean;
  onMessage?: (msg: SSEMessage) => void;
  onRoundComplete?: (round: number, totalRounds: number) => void;
  onComplete?: () => void;
  onError?: (detail: string) => void;
}

const RECONNECT_BASE_MS = 3000;
const RECONNECT_MAX_MS = 30000;

export function useMeetingSSE({
  meetingId,
  enabled,
  onMessage,
  onRoundComplete,
  onComplete,
  onError,
}: UseMeetingSSEOptions) {
  const [connected, setConnected] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryCountRef = useRef(0);
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  // Store callbacks in refs to avoid re-triggering effect
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onRoundCompleteRef = useRef(onRoundComplete);
  onRoundCompleteRef.current = onRoundComplete;
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setConnected(false);
  }, []);

  const connectSSE = useCallback(async () => {
    cleanup();
    if (!enabledRef.current) return;

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`/api/meetings/${meetingId}/stream`, {
        signal: controller.signal,
        headers: { Accept: "text/event-stream" },
      });

      if (!res.ok || !res.body) {
        setConnected(false);
        return;
      }

      setConnected(true);
      retryCountRef.current = 0;  // reset backoff on successful connection
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last incomplete line in buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event: SSEMessage = JSON.parse(line.slice(6));
              switch (event.type) {
                case "message":
                  onMessageRef.current?.(event);
                  break;
                case "round_complete":
                  onRoundCompleteRef.current?.(
                    event.round || 0,
                    event.total_rounds || 0
                  );
                  break;
                case "meeting_complete":
                  onCompleteRef.current?.();
                  cleanup();
                  return;
                case "error":
                  onErrorRef.current?.(event.detail || "Unknown error");
                  cleanup();
                  return;
              }
            } catch {
              // Ignore JSON parse errors
            }
          }
          // Lines starting with ":" are comments (keepalive), ignore them
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      // Connection lost — schedule reconnect
      setConnected(false);
    }

    // Auto-reconnect if still enabled (exponential backoff)
    if (enabledRef.current) {
      setConnected(false);
      const delay = Math.min(RECONNECT_BASE_MS * Math.pow(2, retryCountRef.current), RECONNECT_MAX_MS);
      retryCountRef.current += 1;
      reconnectTimer.current = setTimeout(() => {
        if (enabledRef.current) connectSSE();
      }, delay);
    }
  }, [meetingId, cleanup]);

  useEffect(() => {
    if (enabled) {
      connectSSE();
    } else {
      cleanup();
    }
    return cleanup;
  }, [enabled, meetingId, connectSSE, cleanup]);

  return { connected };
}
