"use client";

import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { MobileGestureProvider } from "@/contexts/MobileGestureContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <TooltipProvider delayDuration={200}>
        <MobileGestureProvider>{children}</MobileGestureProvider>
      </TooltipProvider>
    </ThemeProvider>
  );
}
