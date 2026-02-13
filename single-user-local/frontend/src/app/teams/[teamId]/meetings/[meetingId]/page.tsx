"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { meetingsAPI } from "@/lib/api";
import type { MeetingWithMessages } from "@/types";

export default function MeetingDetailPage() {
  const params = useParams();
  const teamId = params.teamId as string;
  const meetingId = params.meetingId as string;

  const [meeting, setMeeting] = useState<MeetingWithMessages | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [userMessage, setUserMessage] = useState("");
  const [topic, setTopic] = useState("");

  const loadMeeting = async () => {
    try {
      setLoading(true);
      const data = await meetingsAPI.get(meetingId);
      setMeeting(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load meeting");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMeeting();
  }, [meetingId]);

  const handleRun = async () => {
    try {
      setRunning(true);
      setError(null);
      const data = await meetingsAPI.run(meetingId, 1, topic || undefined);
      setMeeting(data);
      setTopic("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run meeting");
    } finally {
      setRunning(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userMessage.trim()) return;
    try {
      await meetingsAPI.addMessage(meetingId, userMessage);
      setUserMessage("");
      loadMeeting();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    }
  };

  if (loading) return <p className="text-gray-500">Loading...</p>;
  if (!meeting) return <p className="text-red-500">Meeting not found</p>;

  const isCompleted = meeting.status === "completed";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href={`/teams/${teamId}`}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          &larr; Back to Team
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">{meeting.title}</h1>
          <span
            className={`text-xs px-2 py-1 rounded ${
              meeting.status === "completed"
                ? "bg-green-100 text-green-700"
                : meeting.status === "running"
                ? "bg-yellow-100 text-yellow-700"
                : meeting.status === "failed"
                ? "bg-red-100 text-red-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {meeting.status}
          </span>
        </div>
        <p className="text-sm text-gray-500 mt-1">
          Round {meeting.current_round}/{meeting.max_rounds}
        </p>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      {/* Messages */}
      <div className="space-y-3">
        {meeting.messages.length === 0 ? (
          <p className="text-gray-500 text-sm">
            No messages yet. Run a round or send a message to start the discussion.
          </p>
        ) : (
          meeting.messages.map((msg) => (
            <div
              key={msg.id}
              className={`p-4 rounded-lg ${
                msg.role === "user"
                  ? "bg-blue-50 border border-blue-200"
                  : "bg-white border border-gray-200"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium text-sm text-gray-900">
                  {msg.role === "user" ? "You" : msg.agent_name || "Assistant"}
                </span>
                <span className="text-xs text-gray-400">
                  Round {msg.round_number}
                </span>
              </div>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">
                {msg.content}
              </p>
            </div>
          ))
        )}
      </div>

      {/* Controls */}
      {!isCompleted && (
        <div className="space-y-3 border-t border-gray-200 pt-4">
          {/* User message input */}
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <input
              type="text"
              value={userMessage}
              onChange={(e) => setUserMessage(e.target.value)}
              placeholder="Send a message to the agents..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Send
            </button>
          </form>

          {/* Run controls */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Discussion topic (optional)"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <button
              onClick={handleRun}
              disabled={running}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? "Running..." : "Run Round"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
