"use client";

import { useCallback, useRef } from "react";

const MIN_SWIPE_DISTANCE = 50;
const MAX_VERTICAL_FOR_HORIZONTAL = 80;
const MAX_HORIZONTAL_FOR_VERTICAL = 80;

type SwipeDirection = "up" | "down" | "left" | "right";

interface SwipeHandlers {
  onSwipeUp?: () => void;
  onSwipeDown?: () => void;
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
}

export function useSwipeGesture(handlers: SwipeHandlers) {
  const start = useRef<{ x: number; y: number } | null>(null);

  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    const t = e.touches[0];
    if (t) start.current = { x: t.clientX, y: t.clientY };
  }, []);

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      const t = e.changedTouches[0];
      if (!t || !start.current) return;
      const dx = t.clientX - start.current.x;
      const dy = t.clientY - start.current.y;
      start.current = null;

      const absDx = Math.abs(dx);
      const absDy = Math.abs(dy);

      if (absDx > absDy) {
        if (absDy > MAX_VERTICAL_FOR_HORIZONTAL) return;
        if (dx > MIN_SWIPE_DISTANCE) handlers.onSwipeRight?.();
        else if (dx < -MIN_SWIPE_DISTANCE) handlers.onSwipeLeft?.();
      } else {
        if (absDx > MAX_HORIZONTAL_FOR_VERTICAL) return;
        if (dy > MIN_SWIPE_DISTANCE) handlers.onSwipeDown?.();
        else if (dy < -MIN_SWIPE_DISTANCE) handlers.onSwipeUp?.();
      }
    },
    [handlers]
  );

  return { onTouchStart: handleTouchStart, onTouchEnd: handleTouchEnd };
}
