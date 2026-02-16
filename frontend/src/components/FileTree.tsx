"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type { CodeArtifact } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ChevronDown,
  ChevronRight,
  File,
  Folder,
  FolderOpen,
  FileCode,
  Trash2,
} from "lucide-react";

interface FileTreeProps {
  artifacts: CodeArtifact[];
  onViewFile: (artifact: CodeArtifact) => void;
  onDeleteFile: (id: string) => void;
  /** Selection for bulk delete */
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onSelectAll?: () => void;
  onClearSelection?: () => void;
  onDeleteSelected?: () => void;
}

interface TreeNode {
  name: string;
  path: string;
  type: "file" | "folder";
  artifact?: CodeArtifact;
  children: TreeNode[];
}

function buildTree(artifacts: CodeArtifact[]): TreeNode {
  const root: TreeNode = {
    name: "root",
    path: "",
    type: "folder",
    children: [],
  };

  for (const artifact of artifacts) {
    const parts = artifact.filename.split("/").filter(Boolean);
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1;
      const path = parts.slice(0, i + 1).join("/");

      let child = current.children.find((c) => c.name === part);
      
      if (!child) {
        child = {
          name: part,
          path,
          type: isFile ? "file" : "folder",
          artifact: isFile ? artifact : undefined,
          children: [],
        };
        current.children.push(child);
      }

      current = child;
    }
  }

  // Sort: folders first, then files, alphabetically
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) {
        return a.type === "folder" ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((node) => {
      if (node.children.length > 0) {
        sortNodes(node.children);
      }
    });
  };

  sortNodes(root.children);
  return root;
}

interface TreeNodeViewProps {
  node: TreeNode;
  level: number;
  onViewFile: (artifact: CodeArtifact) => void;
  onDeleteFile: (id: string) => void;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
}

function TreeNodeView({ node, level, onViewFile, onDeleteFile, selectedIds, onToggleSelect }: TreeNodeViewProps) {
  const [expanded, setExpanded] = useState(level === 0);

  const langColor = (lang: string) => {
    const colors: Record<string, string> = {
      python: "bg-blue-500/10 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400",
      javascript: "bg-yellow-500/10 text-yellow-600 dark:bg-yellow-500/20 dark:text-yellow-400",
      typescript: "bg-blue-600/10 text-blue-700 dark:bg-blue-600/20 dark:text-blue-400",
      bash: "bg-green-500/10 text-green-600 dark:bg-green-500/20 dark:text-green-400",
      shell: "bg-green-500/10 text-green-600 dark:bg-green-500/20 dark:text-green-400",
      yaml: "bg-purple-500/10 text-purple-600 dark:bg-purple-500/20 dark:text-purple-400",
      json: "bg-orange-500/10 text-orange-600 dark:bg-orange-500/20 dark:text-orange-400",
      markdown: "bg-gray-500/10 text-gray-600 dark:bg-gray-500/20 dark:text-gray-400",
    };
    return colors[lang.toLowerCase()] || "bg-muted text-muted-foreground";
  };

  if (node.type === "file" && node.artifact) {
    const id = node.artifact.id;
    const selected = selectedIds?.has(id) ?? false;
    return (
      <div
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-muted/50 cursor-pointer group"
        style={{ paddingLeft: `${level * 1.25 + 0.5}rem` }}
        onClick={() => onViewFile(node.artifact!)}
      >
        {onToggleSelect ? (
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => {
              e.stopPropagation();
              onToggleSelect(id);
            }}
            onClick={(e) => e.stopPropagation()}
            className="h-4 w-4 rounded border-input shrink-0 cursor-pointer"
          />
        ) : (
          <span className="w-4 shrink-0" />
        )}
        <FileCode className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="text-sm flex-1 truncate">{node.name}</span>
        <Badge variant="outline" className={`text-xs ${langColor(node.artifact.language)}`}>
          {node.artifact.language}
        </Badge>
        {node.artifact.version > 1 && (
          <Badge variant="outline" className="text-xs">
            v{node.artifact.version}
          </Badge>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
            e.stopPropagation();
            onDeleteFile(node.artifact!.id);
          }}
        >
          <Trash2 className="h-3.5 w-3.5 text-destructive" />
        </Button>
      </div>
    );
  }

  if (node.type === "folder") {
    const fileCount = countFiles(node);
    return (
      <div>
        <div
          className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-muted/50 cursor-pointer"
          style={{ paddingLeft: `${level * 1.25 + 0.5}rem` }}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
          )}
          {expanded ? (
            <FolderOpen className="h-4 w-4 text-blue-500 shrink-0" />
          ) : (
            <Folder className="h-4 w-4 text-blue-500 shrink-0" />
          )}
          <span className="text-sm font-medium flex-1">{node.name}</span>
          <span className="text-xs text-muted-foreground">
            {fileCount} {fileCount === 1 ? "file" : "files"}
          </span>
        </div>
        {expanded && (
          <div>
            {node.children.map((child) => (
              <TreeNodeView
                key={child.path}
                node={child}
                level={level + 1}
                onViewFile={onViewFile}
                onDeleteFile={onDeleteFile}
                selectedIds={selectedIds}
                onToggleSelect={onToggleSelect}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return null;
}

function countFiles(node: TreeNode): number {
  let count = 0;
  if (node.type === "file") {
    count = 1;
  }
  for (const child of node.children) {
    count += countFiles(child);
  }
  return count;
}

export default function FileTree({
  artifacts,
  onViewFile,
  onDeleteFile,
  selectedIds,
  onToggleSelect,
  onSelectAll,
  onClearSelection,
  onDeleteSelected,
}: FileTreeProps) {
  if (artifacts.length === 0) {
    return null;
  }

  const tree = buildTree(artifacts);
  const selectedCount = selectedIds?.size ?? 0;
  const hasSelection = onToggleSelect && (onSelectAll || onClearSelection || onDeleteSelected);
  const t = useTranslations("meeting");

  return (
    <div className="border rounded-lg flex flex-col min-h-0 max-h-[320px]">
      {hasSelection && (
        <div className="flex items-center gap-2 p-2 border-b bg-muted/30 shrink-0">
          {onSelectAll && (
            <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={onSelectAll}>
              {t("selectAll")}
            </Button>
          )}
          {onClearSelection && (
            <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={onClearSelection}>
              {t("clearSelection")}
            </Button>
          )}
          {selectedCount > 0 && onDeleteSelected && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-destructive hover:text-destructive"
              onClick={onDeleteSelected}
            >
              {t("deleteSelectedCount", { count: selectedCount })}
            </Button>
          )}
        </div>
      )}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-2">
          {tree.children.map((node) => (
            <TreeNodeView
              key={node.path}
              node={node}
              level={0}
              onViewFile={onViewFile}
              onDeleteFile={onDeleteFile}
              selectedIds={selectedIds}
              onToggleSelect={onToggleSelect}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
