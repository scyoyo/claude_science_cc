"use client";

import { cn } from "@/lib/utils";

/**
 * Page header with optional action buttons.
 * On mobile: title and buttons stack vertically; buttons also stack vertically when 2+.
 * Use this pattern for Teams, Agents, Meetings, and future pages with multiple header actions.
 */
export function PageHeaderWithActions({
  title,
  actions,
  className,
}: {
  title: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      {title}
      {actions && (
        <div className="flex flex-col sm:flex-row gap-2">{actions}</div>
      )}
    </div>
  );
}
