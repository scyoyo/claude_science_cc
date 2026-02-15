"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWebSocketBase } from "@/lib/auth";

/** Connection timeout in ms — if WS doesn't open within this, give up. */
const CONNECT_TIMEOUT_MS = 5000;

export interface WSMessage {
  type: string;
  agent_name?: string;
  agent_id?: string;
  content?: string;
  round?: number;
  total_rounds?: number;
  status?: string;
  detail?: string;
  role?: string;
}

interface UseMeetingWSOptions {
  meetingId: string;
  onMessage?: (msg: WSMessage) => void;
  onError?: (error: string) => void;
  onRoundComplete?: (round: number, totalRounds: number) => void;
  onMeetingComplete?: () => void;
  onConnectFailed?: () => void;
}

export function useMeetingWebSocket({
  meetingId,
  onMessage,
  onError,
  onRoundComplete,
  onMeetingComplete,
  onConnectFailed,
}: UseMeetingWSOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [connected, setConnected] = useState(false);
  const [speaking, setSpeaking] = useState<string | null>(null);

  const clearConnectTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    // Close any lingering connection attempt
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    const wsBase = getWebSocketBase();
    const ws = new WebSocket(`${wsBase}/ws/meetings/${meetingId}`);

    // Timeout: if onopen doesn't fire within CONNECT_TIMEOUT_MS, give up
    timeoutRef.current = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        ws.close();
        wsRef.current = null;
        setConnected(false);
        onConnectFailed?.();
      }
    }, CONNECT_TIMEOUT_MS);

    ws.onopen = () => {
      clearConnectTimeout();
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);

      switch (msg.type) {
        case "agent_speaking":
          setSpeaking(msg.agent_name || null);
          break;
        case "message":
          setSpeaking(null);
          onMessage?.(msg);
          break;
        case "message_saved":
          onMessage?.(msg);
          break;
        case "round_complete":
          onRoundComplete?.(msg.round || 0, msg.total_rounds || 0);
          break;
        case "meeting_complete":
          onMeetingComplete?.();
          break;
        case "error":
          onError?.(msg.detail || "Unknown error");
          break;
      }
    };

    ws.onclose = () => {
      clearConnectTimeout();
      setConnected(false);
      setSpeaking(null);
    };

    ws.onerror = () => {
      clearConnectTimeout();
      wsRef.current = null;
      setConnected(false);
      onConnectFailed?.();
    };

    wsRef.current = ws;
  }, [meetingId, onMessage, onError, onRoundComplete, onMeetingComplete, onConnectFailed, clearConnectTimeout]);

  const disconnect = useCallback(() => {
    clearConnectTimeout();
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
    setSpeaking(null);
  }, [clearConnectTimeout]);

  const sendUserMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "user_message", content }));
  }, []);

  const startRound = useCallback((rounds: number = 1, topic?: string, locale?: string) => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(
      JSON.stringify({
        type: "start_round",
        rounds,
        ...(topic ? { topic } : {}),
        ...(locale === "zh" || locale === "en" ? { locale } : {}),
      })
    );
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearConnectTimeout();
      wsRef.current?.close();
    };
  }, [clearConnectTimeout]);

  return {
    connected,
    speaking,
    connect,
    disconnect,
    sendUserMessage,
    startRound,
  };
}
