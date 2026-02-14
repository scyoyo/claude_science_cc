"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
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
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

export default function EditorPage() {
  const params = useParams();
  const teamId = params.teamId as string;
  const t = useTranslations("editor");
  const tc = useTranslations("common");

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

  const handleNodesChange: OnNodesChange = useCallback(
    (changes) => {
      onNodesChange(changes);

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

  if (loading) return <p className="text-muted-foreground">{tc("loading")}</p>;
  if (!team) return <p className="text-destructive">Team not found</p>;

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Button asChild variant="ghost" size="sm">
          <Link href={`/teams/${teamId}`}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            {t("back")}
          </Link>
        </Button>
        <h1 className="text-lg sm:text-xl font-bold truncate">
          {team.name} - {t("title")}
        </h1>
        <span className="ml-auto text-xs sm:text-sm text-muted-foreground hidden sm:block">{t("hint")}</span>
      </div>

      {error && (
        <div className="p-2 mb-2 bg-destructive/10 text-destructive rounded text-sm">{error}</div>
      )}

      <div className="flex-1 flex flex-col md:flex-row gap-4 min-h-0">
        {/* Graph */}
        <div className="flex-1 min-h-[300px] border rounded-lg overflow-hidden bg-card">
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
          <div className="w-full md:w-[400px] lg:w-[500px] md:max-w-[50vw] shrink-0 border rounded-lg bg-card flex flex-col min-h-[300px] md:min-h-0">
            <div className="p-3 border-b">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">{selectedAgent.name}</h2>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setSelectedAgent(null)}
                >
                  &times;
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-1">{selectedAgent.title}</p>
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
            <div className="p-3 border-t flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelectedAgent(null)}>
                {tc("cancel")}
              </Button>
              <Button size="sm" onClick={handleSavePrompt}>
                {t("savePrompt")}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
