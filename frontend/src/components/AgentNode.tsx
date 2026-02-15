"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Badge } from "@/components/ui/badge";
import { getModelLabel } from "@/lib/models";

export interface AgentNodeData {
  agent_id: string;
  name: string;
  title: string;
  model: string;
  expertise: string;
  is_mirror: boolean;
  onEdit: (agentId: string) => void;
  [key: string]: unknown;
}

function AgentNode({ data }: NodeProps) {
  const nodeData = data as unknown as AgentNodeData;

  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[180px] cursor-pointer bg-card text-card-foreground ${
        nodeData.is_mirror
          ? "border-purple-400 dark:border-purple-600"
          : "border-border"
      } hover:border-primary transition-colors`}
      onDoubleClick={() => nodeData.onEdit(nodeData.agent_id)}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="text-sm font-semibold">{nodeData.name}</div>
      <div className="text-xs text-muted-foreground">{nodeData.title}</div>
      <div className="mt-1 flex items-center gap-1">
        <Badge variant="outline" className="text-[10px] px-2 py-0 rounded-full max-w-[90px] truncate">
          {getModelLabel(nodeData.model)}
        </Badge>
        {nodeData.is_mirror && (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            Mirror
          </Badge>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  );
}

export default memo(AgentNode);
