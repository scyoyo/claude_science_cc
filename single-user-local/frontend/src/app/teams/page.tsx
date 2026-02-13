"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { teamsAPI } from "@/lib/api";
import type { Team } from "@/types";

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");

  const loadTeams = async () => {
    try {
      setLoading(true);
      const data = await teamsAPI.list();
      setTeams(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load teams");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTeams();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamName.trim()) return;
    try {
      await teamsAPI.create({ name: newTeamName, description: newTeamDesc });
      setNewTeamName("");
      setNewTeamDesc("");
      setShowCreate(false);
      loadTeams();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create team");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this team and all its agents?")) return;
    try {
      await teamsAPI.delete(id);
      loadTeams();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete team");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          {showCreate ? "Cancel" : "New Team"}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {showCreate && (
        <form onSubmit={handleCreate} className="p-4 bg-white rounded-lg border border-gray-200 space-y-3">
          <input
            type="text"
            value={newTeamName}
            onChange={(e) => setNewTeamName(e.target.value)}
            placeholder="Team name"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
          />
          <input
            type="text"
            value={newTeamDesc}
            onChange={(e) => setNewTeamDesc(e.target.value)}
            placeholder="Description (optional)"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Create Team
          </button>
        </form>
      )}

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : teams.length === 0 ? (
        <p className="text-gray-500">No teams yet. Create one to get started.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {teams.map((team) => (
            <div
              key={team.id}
              className="p-4 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-colors"
            >
              <Link href={`/teams/${team.id}`}>
                <h2 className="text-lg font-semibold text-gray-900 hover:text-blue-600">
                  {team.name}
                </h2>
              </Link>
              {team.description && (
                <p className="mt-1 text-sm text-gray-600 line-clamp-2">
                  {team.description}
                </p>
              )}
              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-gray-400">
                  {new Date(team.created_at).toLocaleDateString()}
                </span>
                <button
                  onClick={() => handleDelete(team.id)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
