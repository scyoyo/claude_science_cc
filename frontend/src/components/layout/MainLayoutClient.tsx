"use client";

import { cn } from "@/lib/utils";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useMobileGesture } from "@/contexts/MobileGestureContext";
import { useSwipeGesture } from "@/hooks/useSwipeGesture";
import { useCallback } from "react";

export function MainLayoutClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isMobile, sidebarOpen, setSidebarOpen } = useMobileGesture();

  const contentSwipe = useSwipeGesture({
    onSwipeRight: useCallback(() => setSidebarOpen(true), [setSidebarOpen]),
    onSwipeLeft: useCallback(() => setSidebarOpen(false), [setSidebarOpen]),
  });

  return (
    <div
      className="flex h-[100dvh] sm:h-screen overflow-hidden bg-background w-full max-w-[100vw]"
      {...(isMobile ? contentSwipe : {})}
    >
      <Sidebar />
      <div
        className={cn(
          "flex flex-1 flex-col overflow-hidden min-w-0 transition-[margin] duration-300 ease-out",
          isMobile && sidebarOpen && "ml-14"
        )}
      >
        <Header />
        <main className="flex-1 overflow-auto p-3 sm:p-6 min-h-0">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
