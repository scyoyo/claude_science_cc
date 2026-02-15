"use client";

import type { CodeArtifact } from "@/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ArtifactViewerProps {
  artifact: CodeArtifact | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function ArtifactViewer({ artifact, open, onOpenChange }: ArtifactViewerProps) {
  if (!artifact) return null;

  const langColor = (lang: string) => {
    const colors: Record<string, string> = {
      python: "bg-blue-500/10 text-blue-600",
      javascript: "bg-yellow-500/10 text-yellow-600",
      typescript: "bg-blue-600/10 text-blue-700",
      bash: "bg-green-500/10 text-green-600",
      shell: "bg-green-500/10 text-green-600",
    };
    return colors[lang.toLowerCase()] || "";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-wrap">
            <span className="truncate">{artifact.filename}</span>
            <Badge variant="outline" className={langColor(artifact.language)}>
              {artifact.language}
            </Badge>
            <Badge variant="outline" className="text-xs">
              v{artifact.version}
            </Badge>
          </DialogTitle>
        </DialogHeader>
        {artifact.description && (
          <p className="text-sm text-muted-foreground">{artifact.description}</p>
        )}
        <ScrollArea className="flex-1 max-h-[60vh] rounded-md border bg-muted/30">
          <pre className="text-xs p-4 overflow-x-auto">
            <code>{artifact.content}</code>
          </pre>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
