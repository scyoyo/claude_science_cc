"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getWebSocketBase } from "@/lib/auth";

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
}

export function useMeetingWebSocket({
  meetingId,
  onMessage,
  onError,
  onRoundComplete,
  onMeetingComplete,
}: UseMeetingWSOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [speaking, setSpeaking] = useState<string | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsBase = getWebSocketBase();
    const ws = new WebSocket(`${wsBase}/ws/meetings/${meetingId}`);

    ws.onopen = () => setConnected(true);

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
      setConnected(false);
      setSpeaking(null);
    };

    ws.onerror = () => {
      onError?.("WebSocket connection failed");
    };

    wsRef.current = ws;
  }, [meetingId, onMessage, onError, onRoundComplete, onMeetingComplete]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
    setSpeaking(null);
  }, []);

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
      wsRef.current?.close();
    };
  }, []);

  return {
    connected,
    speaking,
    connect,
    disconnect,
    sendUserMessage,
    startRound,
  };
}
