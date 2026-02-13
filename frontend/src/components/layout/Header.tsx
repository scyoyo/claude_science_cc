"use client";

import { usePathname } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { ThemeToggle } from "./ThemeToggle";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { Separator } from "@/components/ui/separator";

function useBreadcrumb() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  if (pathname === "/") return t("dashboard");
  const segment = pathname.split("/").filter(Boolean)[0];
  const validSegments = ["teams", "settings", "profile", "onboarding", "meetings"] as const;
  if (segment && validSegments.includes(segment as typeof validSegments[number])) {
    return t(segment as typeof validSegments[number]);
  }
  return t("dashboard");
}

export function Header() {
  const breadcrumb = useBreadcrumb();

  return (
    <header className="flex h-12 items-center border-b border-border/50 px-4">
      {/* Left: Breadcrumb */}
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs tracking-wider text-muted-foreground uppercase">
          Virtual Lab
        </span>
        <Separator orientation="vertical" className="h-4" />
        <span className="text-sm font-medium">{breadcrumb}</span>
      </div>

      {/* Right: Controls */}
      <div className="ml-auto flex items-center gap-1">
        <LocaleSwitcher />
        <ThemeToggle />
      </div>
    </header>
  );
}
