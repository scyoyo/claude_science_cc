"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { dashboardAPI } from "@/lib/api";
import type { DashboardStats } from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  Bot,
  MessageSquare,
  Code,
  Wand2,
  Plus,
  Settings,
  Workflow,
} from "lucide-react";

function StatCard({
  label,
  value,
  icon: Icon,
  href,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  href?: string;
}) {
  const content = (
    <CardContent className="flex items-center gap-4 py-5">
      <div className="rounded-lg bg-primary/10 p-2.5">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div>
        <p className="text-2xl font-bold">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
    </CardContent>
  );
  if (href) {
    return (
      <Link href={href}>
        <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full">
          {content}
        </Card>
      </Link>
    );
  }
  return <Card>{content}</Card>;
}

function FallbackCards({ t }: { t: ReturnType<typeof useTranslations<"home">> }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <Link href="/onboarding">
        <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Wand2 className="h-5 w-5 text-primary" />
              <div>
                <CardTitle>{t("onboardingCard.title")}</CardTitle>
                <CardDescription className="mt-1">{t("onboardingCard.description")}</CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      </Link>
      <Link href="/teams">
        <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Users className="h-5 w-5 text-primary" />
              <div>
                <CardTitle>{t("teamsCard.title")}</CardTitle>
                <CardDescription className="mt-1">{t("teamsCard.description")}</CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      </Link>
      <Link href="/settings">
        <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Settings className="h-5 w-5 text-primary" />
              <div>
                <CardTitle>{t("settingsCard.title")}</CardTitle>
                <CardDescription className="mt-1">{t("settingsCard.description")}</CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      </Link>
      <Link href="/teams">
        <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer h-full opacity-90">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Workflow className="h-5 w-5 text-muted-foreground" />
              <div>
                <CardTitle>{t("editorCard.title")}</CardTitle>
                <CardDescription className="mt-1">{t("editorCard.description")}</CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      </Link>
    </div>
  );
}

export default function DashboardPage() {
  const t = useTranslations("home");
  const td = useTranslations("dashboard");
  const tc = useTranslations("common");

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    dashboardAPI.stats().then(setStats).catch(() => setError(true));
  }, []);

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed":
        return "secondary" as const;
      case "running":
        return "default" as const;
      case "failed":
        return "destructive" as const;
      default:
        return "outline" as const;
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-muted-foreground">{t("subtitle")}</p>
      </div>

      {error || !stats ? (
        <FallbackCards t={t} />
      ) : (
        <>
          {/* Stats Row - each card links to corresponding page */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label={td("teams")}
              value={stats.total_teams}
              icon={Users}
              href="/teams"
            />
            <StatCard
              label={td("agents")}
              value={stats.total_agents}
              icon={Bot}
              href="/teams"
            />
            <StatCard
              label={td("meetings")}
              value={stats.total_meetings}
              icon={MessageSquare}
              href="/meetings"
            />
            <StatCard
              label={td("artifacts")}
              value={stats.total_artifacts}
              icon={Code}
              href="/meetings"
            />
          </div>

          {/* Quick Actions - buttons link to pages */}
          <div className="flex flex-col sm:flex-row gap-3">
            <Button asChild>
              <Link href="/onboarding">
                <Wand2 className="h-4 w-4 mr-2" />
                {td("newProject")}
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/teams">
                <Plus className="h-4 w-4 mr-2" />
                {td("newTeam")}
              </Link>
            </Button>
          </div>

          {/* Two-column: Recent Meetings + Teams Overview */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Meetings */}
            <Card>
              <CardHeader>
                <CardTitle>{td("recentMeetings")}</CardTitle>
              </CardHeader>
              <CardContent>
                {stats.recent_meetings.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{td("noRecentMeetings")}</p>
                ) : (
                  <div className="space-y-3">
                    {stats.recent_meetings.map((m) => (
                      <Link
                        key={m.id}
                        href={`/teams/${m.team_id}/meetings/${m.id}`}
                        className="flex items-center justify-between p-3 rounded-lg border hover:border-primary/50 transition-colors"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium truncate">{m.title}</p>
                          <p className="text-xs text-muted-foreground truncate">{m.team_name}</p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0 ml-3">
                          <Badge variant={statusVariant(m.status)}>{m.status}</Badge>
                          <span className="text-xs text-muted-foreground">
                            {m.current_round}/{m.max_rounds}
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Teams Overview */}
            <Card>
              <CardHeader>
                <CardTitle>{td("teamsOverview")}</CardTitle>
              </CardHeader>
              <CardContent>
                {stats.teams_overview.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{td("noTeams")}</p>
                ) : (
                  <div className="space-y-3">
                    {stats.teams_overview.map((team) => (
                      <Link
                        key={team.id}
                        href={`/teams/${team.id}`}
                        className="flex items-center justify-between p-3 rounded-lg border hover:border-primary/50 transition-colors"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium truncate">{team.name}</p>
                          {team.description && (
                            <p className="text-xs text-muted-foreground truncate">
                              {team.description}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-3 shrink-0 ml-3 text-xs text-muted-foreground">
                          <span>
                            {team.agent_count} {td("agents").toLowerCase()}
                          </span>
                          <span>
                            {team.meeting_count} {td("meetings").toLowerCase()}
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
