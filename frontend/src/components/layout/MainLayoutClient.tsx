"use client";

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
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-3 sm:p-6 min-h-0">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>
      {/* Mobile sidebar backdrop */}
      {isMobile && (
        <div
          className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 md:hidden ${
            sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
          onClick={() => setSidebarOpen(false)}
          aria-hidden
        />
      )}
    </div>
  );
}
