"use client";

import dynamic from "next/dynamic";

const EditorPageContent = dynamic(() => import("./EditorPageContent"), {
  ssr: false,
  loading: () => (
    <div className="h-[calc(100vh-120px)] flex flex-col animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-8 w-20 bg-muted rounded" />
        <div className="h-6 w-48 bg-muted rounded" />
      </div>
      <div className="flex-1 border rounded-lg bg-muted" />
    </div>
  ),
});

export default function EditorPage() {
  return <EditorPageContent />;
}
