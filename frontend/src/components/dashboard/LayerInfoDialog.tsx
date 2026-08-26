"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import useSWR from "swr";
import { getLayer } from "@/services/api";
import { Loader2, Layers } from "lucide-react";

interface LayerInfoDialogProps {
  jobId: string | null;
  layerId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export function LayerInfoDialog({ jobId, layerId, isOpen, onClose }: LayerInfoDialogProps) {
  const swrKey = isOpen && jobId && layerId ? [jobId, layerId] as const : null;
  const { data: layer, isLoading, error } = useSWR(
    swrKey,
    ([jId, lId]) => getLayer(jId, lId)
  );

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl bg-surface-deep border-border/50 shadow-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Layers className="size-4 text-muted-foreground" />
            Layer Details
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-6 mt-2">
          {isLoading ? (
            <div className="h-32 flex items-center justify-center text-muted-foreground">
              <Loader2 className="animate-spin size-6" />
            </div>
          ) : layer ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Name</span>
                  <span className="text-sm font-medium text-foreground">{layer.name}</span>
                </div>
                {layer.scene_path && (
                  <div className="flex flex-col gap-1.5">
                    <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Scene Path</span>
                    <span className="text-sm font-medium text-foreground truncate" title={layer.scene_path}>{layer.scene_path}</span>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-4 gap-4 bg-muted/20 p-4 rounded-md border border-border/50">
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Cores</span>
                  <span className="text-sm font-medium text-foreground">{layer.min_cores || "Any"}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">RAM (MB)</span>
                  <span className="text-sm font-medium text-foreground">{layer.min_memory_mb || "Any"}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">GPUs</span>
                  <span className="text-sm font-medium text-foreground">{layer.min_gpus || "Any"}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Chunk Size</span>
                  <span className="text-sm font-medium text-foreground">{layer.chunk_size || 1}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Retries</span>
                  <span className="text-sm font-medium text-foreground">{layer.max_retries || 0}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Timeout (s)</span>
                  <span className="text-sm font-medium text-foreground">{layer.timeout_seconds || "None"}</span>
                </div>
                <div className="flex flex-col gap-1 col-span-2">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">Tags</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {layer.tags && layer.tags.length > 0 ? layer.tags.map((tag: string) => (
                      <span key={tag} className="text-[11px] bg-primary/20 text-primary px-1.5 py-0.5 rounded">{tag}</span>
                    )) : <span className="text-sm font-medium text-foreground">None</span>}
                  </div>
                </div>
              </div>
              
              <div className="flex flex-col gap-1.5">
                <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Command</span>
                <div className="bg-muted/30 border border-border/50 rounded-md p-4 max-h-[300px] overflow-y-auto">
                  <pre className="text-xs font-mono text-foreground/90 whitespace-pre-wrap break-all">
                    {layer.command || "No command available"}
                  </pre>
                </div>
              </div>
            </>
          ) : error ? (
            <div className="h-32 flex flex-col items-center justify-center text-destructive gap-2">
              <span className="text-sm font-semibold">Failed to load layer details</span>
              <span className="text-xs text-muted-foreground">{error?.message || "An unknown error occurred."}</span>
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
