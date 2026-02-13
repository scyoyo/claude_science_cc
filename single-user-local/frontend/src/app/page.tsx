import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Virtual Lab</h1>
        <p className="mt-2 text-gray-600">
          AI-powered virtual research lab for multi-agent collaboration
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          href="/teams"
          className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all"
        >
          <h2 className="text-lg font-semibold text-gray-900">Teams</h2>
          <p className="mt-1 text-sm text-gray-600">
            Create and manage virtual lab teams with AI agents
          </p>
        </Link>

        <Link
          href="/settings"
          className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-all"
        >
          <h2 className="text-lg font-semibold text-gray-900">Settings</h2>
          <p className="mt-1 text-sm text-gray-600">
            Configure API keys and model preferences
          </p>
        </Link>

        <div className="p-6 bg-white rounded-lg border border-gray-200 opacity-60">
          <h2 className="text-lg font-semibold text-gray-900">Visual Editor</h2>
          <p className="mt-1 text-sm text-gray-600">
            Drag-and-drop agent graph editor (coming soon)
          </p>
        </div>
      </div>
    </div>
  );
}
