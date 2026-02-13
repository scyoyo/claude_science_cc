"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type OnNodesChange,
  addEdge,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Editor from "@monaco-editor/react";
import { teamsAPI, agentsAPI } from "@/lib/api";
import type { Agent, TeamWithAgents } from "@/types";
import AgentNode from "@/components/AgentNode";

export default function EditorPage() {
  const params = useParams();
  const teamId = params.teamId as string;

  const [team, setTeam] = useState<TeamWithAgents | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [editedPrompt, setEditedPrompt] = useState("");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const nodeTypes = useMemo(() => ({ agent: AgentNode }), []);

  const handleEditAgent = useCallback(
    (agentId: string) => {
      const agent = team?.agents.find((a) => a.id === agentId);
      if (agent) {
        setSelectedAgent(agent);
        setEditedPrompt(agent.system_prompt);
      }
    },
    [team]
  );

  const loadTeam = useCallback(async () => {
    try {
      setLoading(true);
      const data = await teamsAPI.get(teamId);
      setTeam(data);

      // Convert agents to React Flow nodes
      const newNodes: Node[] = data.agents.map((agent, index) => ({
        id: agent.id,
        type: "agent",
        position: {
          x: agent.position_x || (index % 3) * 250 + 50,
          y: agent.position_y || Math.floor(index / 3) * 200 + 50,
        },
        data: {
          agent_id: agent.id,
          name: agent.name,
          title: agent.title,
          model: agent.model,
          expertise: agent.expertise,
          is_mirror: agent.is_mirror,
          onEdit: handleEditAgent,
        },
      }));

      // Create edges for mirror agents
      const newEdges: Edge[] = data.agents
        .filter((a) => a.is_mirror && a.primary_agent_id)
        .map((a) => ({
          id: `e-${a.primary_agent_id}-${a.id}`,
          source: a.primary_agent_id!,
          target: a.id,
          animated: true,
          style: { stroke: "#9333ea" },
        }));

      setNodes(newNodes);
      setEdges(newEdges);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load team");
    } finally {
      setLoading(false);
    }
  }, [teamId, handleEditAgent, setNodes, setEdges]);

  useEffect(() => {
    loadTeam();
  }, [loadTeam]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  // Save node positions when dragging stops
  const handleNodesChange: OnNodesChange = useCallback(
    (changes) => {
      onNodesChange(changes);

      // Save positions for drag-end changes
      for (const change of changes) {
        if (change.type === "position" && change.dragging === false && change.position) {
          agentsAPI.update(change.id, {
            position_x: change.position.x,
            position_y: change.position.y,
          } as Record<string, unknown>).catch(() => {});
        }
      }
    },
    [onNodesChange]
  );

  const handleSavePrompt = async () => {
    if (!selectedAgent) return;
    try {
      await agentsAPI.update(selectedAgent.id, {
        system_prompt: editedPrompt,
      } as Record<string, unknown>);
      setSelectedAgent(null);
      loadTeam();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  };

  if (loading) return <p className="text-gray-500">Loading...</p>;
  if (!team) return <p className="text-red-500">Team not found</p>;

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Link
            href={`/teams/${teamId}`}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            &larr; Back
          </Link>
          <h1 className="text-xl font-bold text-gray-900">
            {team.name} - Visual Editor
          </h1>
        </div>
        <span className="text-sm text-gray-500">
          Double-click an agent to edit its prompt
        </span>
      </div>

      {error && (
        <div className="p-2 mb-2 bg-red-50 text-red-700 rounded text-sm">{error}</div>
      )}

      <div className="flex-1 flex gap-4">
        {/* Graph */}
        <div className="flex-1 border border-gray-200 rounded-lg overflow-hidden bg-white">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={handleNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>

        {/* Prompt Editor Panel */}
        {selectedAgent && (
          <div className="w-[500px] border border-gray-200 rounded-lg bg-white flex flex-col">
            <div className="p-3 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">
                  {selectedAgent.name}
                </h2>
                <button
                  onClick={() => setSelectedAgent(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  &times;
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">{selectedAgent.title}</p>
            </div>
            <div className="flex-1">
              <Editor
                height="100%"
                defaultLanguage="markdown"
                value={editedPrompt}
                onChange={(value) => setEditedPrompt(value || "")}
                options={{
                  minimap: { enabled: false },
                  wordWrap: "on",
                  lineNumbers: "off",
                  fontSize: 13,
                }}
              />
            </div>
            <div className="p-3 border-t border-gray-200 flex justify-end gap-2">
              <button
                onClick={() => setSelectedAgent(null)}
                className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSavePrompt}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Save Prompt
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
