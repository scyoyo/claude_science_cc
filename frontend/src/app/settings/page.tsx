"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface APIKeyInfo {
  id: string;
  provider: string;
  is_active: boolean;
  key_preview: string;
  created_at: string;
}

export default function SettingsPage() {
  const [keys, setKeys] = useState<APIKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");

  const loadKeys = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/llm/api-keys`);
      if (!res.ok) throw new Error("Failed to load API keys");
      setKeys(await res.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/llm/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to add key");
      }
      setApiKey("");
      loadKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add key");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`${API_BASE}/llm/api-keys/${id}`, { method: "DELETE" });
      loadKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete key");
    }
  };

  return (
    <div className="space-y-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* API Keys */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">API Keys</h2>

        <form onSubmit={handleAdd} className="p-4 bg-white rounded-lg border border-gray-200 space-y-3 mb-4">
          <div className="flex gap-3">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="deepseek">DeepSeek</option>
            </select>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="API key"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Add
            </button>
          </div>
        </form>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : keys.length === 0 ? (
          <p className="text-gray-500 text-sm">No API keys configured.</p>
        ) : (
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                key={key.id}
                className="p-3 bg-white rounded-lg border border-gray-200 flex items-center justify-between"
              >
                <div>
                  <span className="font-medium text-gray-900 capitalize">
                    {key.provider}
                  </span>
                  <span className="ml-2 text-sm text-gray-500">{key.key_preview}</span>
                  {!key.is_active && (
                    <span className="ml-2 text-xs text-red-500">(inactive)</span>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(key.id)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
