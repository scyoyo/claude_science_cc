"use client";

import { usePathname, Link } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import {
  FlaskConical,
  Users,
  Settings,
  UserCircle,
  LayoutDashboard,
  Wand2,
  MessageSquare,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useAuth } from "@/contexts/AuthContext";

const navItems = [
  { key: "onboarding", href: "/onboarding", icon: Wand2 },
  { key: "dashboard", href: "/", icon: LayoutDashboard },
  { key: "teams", href: "/teams", icon: Users },
  { key: "meetings", href: "/meetings", icon: MessageSquare },
  { key: "settings", href: "/settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");
  const { user } = useAuth();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside className="flex h-screen w-14 flex-col border-r border-border/50 bg-background">
      {/* Logo */}
      <div className="flex h-12 items-center justify-center border-b border-border/50">
        <Link href="/">
          <FlaskConical className="h-5 w-5 text-primary" />
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col items-center gap-1 py-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <Tooltip key={item.key}>
              <TooltipTrigger asChild>
                <Link
                  href={item.href}
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-md transition-colors duration-200",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="sr-only">{t(item.key)}</span>
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                {t(item.key)}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>

      {/* Profile at bottom */}
      {user && (
        <div className="flex flex-col items-center gap-1 py-3 border-t border-border/50">
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                href="/profile"
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-md transition-colors duration-200",
                  isActive("/profile")
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                )}
              >
                <UserCircle className="h-4 w-4" />
                <span className="sr-only">{t("profile")}</span>
              </Link>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={8}>
              {t("profile")}
            </TooltipContent>
          </Tooltip>
        </div>
      )}
    </aside>
  );
}
