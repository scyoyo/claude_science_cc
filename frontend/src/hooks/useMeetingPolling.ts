"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { meetingsAPI } from "@/lib/api";

interface MeetingStatus {
  meeting_id: string;
  status: string;
  current_round: number;
  max_rounds: number;
  message_count: number;
  background_running: boolean;
}

interface UseMeetingPollingOptions {
  meetingId: string;
  enabled: boolean;
  intervalMs?: number;
  onStatusChange?: (status: MeetingStatus) => void;
  onComplete?: () => void;
}

export function useMeetingPolling({
  meetingId,
  enabled,
  intervalMs = 3000,
  onStatusChange,
  onComplete,
}: UseMeetingPollingOptions) {
  const [status, setStatus] = useState<MeetingStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevStatusRef = useRef<string | null>(null);

  const poll = useCallback(async () => {
    try {
      const s = await meetingsAPI.status(meetingId);
      setStatus(s);

      onStatusChange?.(s);

      // Detect completion
      if (
        prevStatusRef.current === "running" &&
        (s.status === "completed" || s.status === "pending" || s.status === "failed") &&
        !s.background_running
      ) {
        onComplete?.();
      }
      prevStatusRef.current = s.status;

      // Stop polling if no longer running
      if (!s.background_running && s.status !== "running") {
        setPolling(false);
      }
    } catch {
      // Silently ignore poll errors
    }
  }, [meetingId, onStatusChange, onComplete]);

  useEffect(() => {
    if (enabled) {
      setPolling(true);
      prevStatusRef.current = null;
      // Immediate first poll
      poll();
    } else {
      setPolling(false);
    }
  }, [enabled, poll]);

  useEffect(() => {
    if (polling) {
      timerRef.current = setInterval(poll, intervalMs);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [polling, poll, intervalMs]);

  return { status, polling };
}
