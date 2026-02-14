"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { searchAPI } from "@/lib/api";
import type { Team, Agent } from "@/types";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Users, Bot, Search } from "lucide-react";

export default function SearchPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useTranslations("search");
  const tc = useTranslations("common");
  const inputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState(searchParams.get("q") || "");
  const [teams, setTeams] = useState<Team[]>([]);
  const [agents, setAgents] = useState<(Agent & { team_name?: string })[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setTeams([]);
      setAgents([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    try {
      const [teamsRes, agentsRes] = await Promise.all([
        searchAPI.teams(q),
        searchAPI.agents(q),
      ]);
      setTeams(teamsRes.items);
      setAgents(agentsRes.items as (Agent & { team_name?: string })[]);
      setSearched(true);
    } catch {
      // silently fail on search errors
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    inputRef.current?.focus();
    // If URL has ?q=, search immediately
    const initial = searchParams.get("q");
    if (initial) doSearch(initial);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 300);
  };

  const totalResults = teams.length + agents.length;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={t("placeholder")}
          className="pl-9"
        />
      </div>

      {loading && (
        <p className="text-muted-foreground text-sm">{tc("loading")}</p>
      )}

      {!loading && !searched && !query.trim() && (
        <p className="text-muted-foreground text-sm">{t("typeToSearch")}</p>
      )}

      {!loading && searched && totalResults === 0 && (
        <p className="text-muted-foreground text-sm">
          {t("noResults", { query })}
        </p>
      )}

      {/* Teams Results */}
      {teams.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Users className="h-4 w-4" />
            {t("teamsSection")} ({teams.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {teams.map((team) => (
              <Card
                key={team.id}
                className="hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => router.push(`/teams/${team.id}`)}
              >
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Users className="h-4 w-4 shrink-0" />
                    {team.name}
                  </CardTitle>
                  {team.description && (
                    <CardDescription className="line-clamp-2">
                      {team.description}
                    </CardDescription>
                  )}
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Agents Results */}
      {agents.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <Bot className="h-4 w-4" />
            {t("agentsSection")} ({agents.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {agents.map((agent) => (
              <Card
                key={agent.id}
                className="hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => router.push(`/teams/${agent.team_id}`)}
              >
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Bot className="h-4 w-4 shrink-0" />
                    {agent.name}
                  </CardTitle>
                  <CardDescription>
                    <span className="line-clamp-1">{agent.title}</span>
                    {agent.team_name && (
                      <span className="text-xs text-muted-foreground block mt-0.5">
                        {t("inTeam", { team: agent.team_name })}
                      </span>
                    )}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
