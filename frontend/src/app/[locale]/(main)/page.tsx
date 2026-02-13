"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Users, Settings, Workflow, Wand2 } from "lucide-react";

export default function Home() {
  const t = useTranslations("home");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="mt-2 text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Link href="/onboarding">
          <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Wand2 className="h-5 w-5 text-primary" />
                <div>
                  <CardTitle>{t("onboardingCard.title")}</CardTitle>
                  <CardDescription className="mt-1">
                    {t("onboardingCard.description")}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
        </Link>

        <Link href="/teams">
          <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Users className="h-5 w-5 text-primary" />
                <div>
                  <CardTitle>{t("teamsCard.title")}</CardTitle>
                  <CardDescription className="mt-1">
                    {t("teamsCard.description")}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
        </Link>

        <Link href="/settings">
          <Card className="hover:border-primary/50 hover:shadow-md transition-all cursor-pointer">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Settings className="h-5 w-5 text-primary" />
                <div>
                  <CardTitle>{t("settingsCard.title")}</CardTitle>
                  <CardDescription className="mt-1">
                    {t("settingsCard.description")}
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
        </Link>

        <Card className="opacity-60">
          <CardHeader>
            <div className="flex items-center gap-3">
              <Workflow className="h-5 w-5 text-muted-foreground" />
              <div>
                <CardTitle>{t("editorCard.title")}</CardTitle>
                <CardDescription className="mt-1">
                  {t("editorCard.description")}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}
