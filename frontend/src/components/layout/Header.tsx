"use client";

import { useEffect } from "react";
import { usePathname } from "@/i18n/navigation";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { ThemeToggle } from "./ThemeToggle";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Menu } from "lucide-react";
import { useMobileGesture } from "@/contexts/MobileGestureContext";

function useBreadcrumb() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  if (pathname === "/" || pathname === "/dashboard") return t("dashboard");
  const segment = pathname.split("/").filter(Boolean)[0];
  const validSegments = ["teams", "settings", "profile", "onboarding", "meetings", "search", "dashboard"] as const;
  if (segment && validSegments.includes(segment as typeof validSegments[number])) {
    return t(segment as typeof validSegments[number]);
  }
  return t("dashboard");
}

export function Header() {
  const breadcrumb = useBreadcrumb();
  const router = useRouter();
  const { isMobile, toggleSidebar } = useMobileGesture();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        router.push("/search");
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router]);

  return (
    <header className="flex h-12 shrink-0 items-center border-b border-border/50 px-3 sm:px-4">
      {/* Left: Hamburger (mobile) + Breadcrumb */}
      <div className="flex items-center gap-2 min-w-0">
        {isMobile && (
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={toggleSidebar}
            aria-label="Toggle menu"
          >
            <Menu className="h-4 w-4" />
          </Button>
        )}
        <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase shrink-0 hidden sm:inline">
          Virtual Lab
        </span>
        {!isMobile && <Separator orientation="vertical" className="h-4" />}
        <span className="text-sm font-medium truncate">{breadcrumb}</span>
      </div>

      {/* Right: Controls */}
      <div className="ml-auto flex items-center gap-1 shrink-0">
        <LocaleSwitcher />
        <ThemeToggle />
      </div>
    </header>
  );
}
