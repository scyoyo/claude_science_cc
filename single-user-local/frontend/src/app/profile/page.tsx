"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { getAuthHeaders } from "@/lib/auth";

const API_BASE = "/api";

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) return <p className="text-gray-500">Loading...</p>;

  if (!user) {
    router.push("/login");
    return null;
  }

  function startEdit() {
    setEmail(user!.email);
    setUsername(user!.username);
    setPassword("");
    setEditing(true);
    setError("");
    setSuccess("");
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    const body: Record<string, string> = {};
    if (email !== user!.email) body.email = email;
    if (username !== user!.username) body.username = username;
    if (password) body.password = password;

    if (Object.keys(body).length === 0) {
      setEditing(false);
      setSubmitting(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Update failed");
      }
      setSuccess("Profile updated. Refresh to see changes.");
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Profile</h1>

      {error && <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}
      {success && <div className="p-3 bg-green-50 text-green-700 rounded-lg text-sm">{success}</div>}

      <div className="bg-white p-6 rounded-lg shadow space-y-4">
        {!editing ? (
          <>
            <div>
              <label className="text-sm text-gray-500">Username</label>
              <p className="text-gray-900 font-medium">{user.username}</p>
            </div>
            <div>
              <label className="text-sm text-gray-500">Email</label>
              <p className="text-gray-900">{user.email}</p>
            </div>
            <div>
              <label className="text-sm text-gray-500">Role</label>
              <p className="text-gray-900">{user.is_admin ? "Admin" : "User"}</p>
            </div>
            <div>
              <label className="text-sm text-gray-500">Member since</label>
              <p className="text-gray-900">{new Date(user.created_at).toLocaleDateString()}</p>
            </div>
            <div className="flex gap-3 pt-2">
              <button
                onClick={startEdit}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                Edit Profile
              </button>
              <button
                onClick={() => { logout(); router.push("/login"); }}
                className="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 text-sm"
              >
                Logout
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                minLength={3}
                pattern="^[a-zA-Z0-9_-]+$"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                New Password (leave blank to keep current)
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Min 8 characters"
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
              >
                {submitting ? "Saving..." : "Save Changes"}
              </button>
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
