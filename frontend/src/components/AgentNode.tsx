"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

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
      className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[180px] cursor-pointer ${
        nodeData.is_mirror
          ? "bg-purple-50 border-purple-300"
          : "bg-white border-gray-300"
      } hover:border-blue-400 transition-colors`}
      onDoubleClick={() => nodeData.onEdit(nodeData.agent_id)}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-400" />
      <div className="text-sm font-semibold text-gray-900">{nodeData.name}</div>
      <div className="text-xs text-gray-500">{nodeData.title}</div>
      <div className="mt-1 flex items-center gap-1">
        <span className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">
          {nodeData.model}
        </span>
        {nodeData.is_mirror && (
          <span className="text-xs px-1.5 py-0.5 bg-purple-100 text-purple-600 rounded">
            Mirror
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400" />
    </div>
  );
}

export default memo(AgentNode);
