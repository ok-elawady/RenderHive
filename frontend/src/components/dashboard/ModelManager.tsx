"use client";

import { useRef, useEffect } from "react";
import { CloudDownload, Database, Play, Trash2, RefreshCw, HardDrive, PowerOff } from "lucide-react";
import { toast } from "sonner";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  fetchModels,
  startModelDownload,
  fetchDownloadProgress,
  loadAiModel,
  deleteAiModel,
  cancelModelDownload,
  unloadAiModel,
  type CuratedModel,
} from "@/services/api";

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

import useSWR from "swr";

export function ModelManager({ onModelChanged }: { onModelChanged: () => void }) {
  const {
    data: modelsData,
    error: modelsError,
    isLoading: isModelsLoading,
    mutate: mutateModels,
  } = useSWR("/api/v1/models", fetchModels, {
    revalidateOnFocus: true,
  });

  const { data: progress, mutate: mutateProgress } = useSWR("/api/v1/models/download/progress", fetchDownloadProgress);

  // Robust polling mechanism that survives page refreshes and avoids SWR interval bugs
  useEffect(() => {
    if (!progress?.is_downloading) return;
    const interval = setInterval(() => {
      void mutateProgress();
    }, 1000);
    return () => clearInterval(interval);
  }, [progress?.is_downloading, mutateProgress]);

  const prevProgressRef = useRef<typeof progress | null>(null);

  useEffect(() => {
    const prev = prevProgressRef.current;
    if (prev?.is_downloading && progress && !progress.is_downloading) {
      // Transitioned from downloading to finished/cancelled
      if (progress.error) {
        if (progress.error.toLowerCase().includes("cancelled")) {
          toast.info("Download cancelled");
        } else {
          toast.error("Download failed", { description: progress.error });
        }
      } else if (progress.filename) {
        toast.success("Download complete", { description: `${progress.filename} is ready.` });
        void mutateModels();
      }
    }
    prevProgressRef.current = progress;
  }, [progress, mutateModels]);

  const curated = modelsData?.curated || [];
  const local = modelsData?.local || [];
  const activePath = modelsData?.active_path || "";
  const isLoading = isModelsLoading;
  const isOffline = !!modelsError;

  const handleDownload = async (model: CuratedModel) => {
    if (progress?.is_downloading) {
      toast.error("A download is already in progress.");
      return;
    }
    try {
      await startModelDownload(model.url, model.filename);
      toast.info(`Started downloading ${model.name}`);
      mutateProgress();
    } catch (err: unknown) {
      const e = err as Error;
      toast.error("Failed to start download", { description: e.message });
    }
  };

  const handleCancelDownload = async () => {
    try {
      toast.info("Cancelling...");
      await cancelModelDownload();
      // Polling loop will detect cancellation and clear state/interval gracefully.
    } catch (err: unknown) {
      const e = err as Error;
      toast.error("Failed to cancel download", { description: e.message });
    }
  };

  const handleLoad = async (filename: string, template: string = "mistral") => {
    toast.promise(loadAiModel(filename, template), {
      loading: `Loading ${filename} into memory...`,
      success: () => {
        mutateModels();
        onModelChanged(); // tell parent to refresh health
        return `Loaded ${filename} successfully.`;
      },
      error: (err: unknown) => {
        const e = err as Error;
        return `Failed to load model: ${e.message}`;
      },
    });
  };

  const handleUnload = async () => {
    try {
      toast.info("Unloading active model...");
      await unloadAiModel();
      toast.success("Model unloaded successfully");
      mutateModels();
      onModelChanged();
    } catch (err: unknown) {
      const e = err as Error;
      toast.error("Failed to unload model", { description: e.message });
    }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    try {
      await deleteAiModel(filename);
      toast.success(`Deleted ${filename}`);
      mutateModels();
      onModelChanged();
    } catch (err: unknown) {
      const e = err as Error;
      toast.error("Failed to delete model", { description: e.message });
    }
  };

  const isModelActive = (filename: string) => {
    return activePath.endsWith(filename);
  };

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="p-10 flex items-center justify-center">
          <RefreshCw className="animate-spin text-muted-foreground" />
        </div>
      );
    }

    if (isOffline) {
      return (
        <div className="p-10 flex flex-col items-center justify-center space-y-4">
          <div className="text-destructive font-semibold">AI Scheduler Service Offline</div>
          <div className="text-sm text-muted-foreground text-center">
            Could not connect to the AI scheduling service. Please check if it&apos;s running.
          </div>
          <Button variant="outline" onClick={() => void mutateModels()} className="gap-2">
            <RefreshCw size={14} /> Retry
          </Button>
        </div>
      );
    }

    return (
      <div className="flex flex-col">
        {/* Active Download Banner */}
        {progress?.is_downloading && (
          <div className="bg-primary/5 border-b border-primary/20 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs font-semibold">
              <div className="flex items-center gap-4">
                <span className="text-primary flex items-center gap-2">
                  <CloudDownload size={14} className="animate-bounce" />
                  Downloading {progress.filename}
                </span>
                <span className="text-muted-foreground font-mono">{formatBytes(progress.speed_bps)}/s</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                onClick={handleCancelDownload}
              >
                &times;
              </Button>
            </div>
            <Progress
              value={progress.total_bytes ? (progress.bytes_downloaded / progress.total_bytes) * 100 : 0}
              className="h-2"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>
                {formatBytes(progress.bytes_downloaded)} / {formatBytes(progress.total_bytes)}
              </span>
              <span>
                {progress.total_bytes ? Math.round((progress.bytes_downloaded / progress.total_bytes) * 100) : 0}%
              </span>
            </div>
          </div>
        )}

        <div className="divide-y divide-border/50">
          {/* Local Models */}
          {local.length > 0 && (
            <div className="px-5 py-4 space-y-4">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <HardDrive size={14} className="text-muted-foreground" />
                Local Storage
              </h3>
              <div className="space-y-2">
                {local.map((l) => {
                  const isActive = isModelActive(l.filename);
                  return (
                    <div
                      key={l.filename}
                      className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/20 p-3"
                    >
                      <div>
                        <div className="font-medium text-sm flex items-center gap-2">
                          {l.filename}
                          {isActive && (
                            <Badge
                              variant="outline"
                              className="text-[10px] h-5 border-success text-success bg-success/10 px-1"
                            >
                              Active
                            </Badge>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5">
                          {formatBytes(l.size_bytes)}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!isActive && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 gap-1.5 text-primary hover:text-primary hover:bg-primary/10"
                            onClick={() => {
                              const template = curated.find((c) => c.filename === l.filename)?.template || "mistral";
                              handleLoad(l.filename, template);
                            }}
                          >
                            <Play size={14} /> Load
                          </Button>
                        )}
                        {isActive && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 gap-1.5 text-amber-500 hover:text-amber-500 hover:bg-amber-500/10"
                            onClick={handleUnload}
                            title="Unload model"
                          >
                            <PowerOff size={14} /> Unload
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 gap-1.5 text-destructive hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDelete(l.filename)}
                          disabled={isActive}
                          title={isActive ? "Unload model before deleting" : "Delete model"}
                        >
                          <Trash2 size={14} /> Delete
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Curated Models */}
          <div className="p-4 space-y-4">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <CloudDownload size={14} className="text-muted-foreground" />
              Available Models
            </h3>
            <div className="grid gap-4 sm:grid-cols-2">
              {curated.map((m) => {
                const isDownloaded = local.some((l) => l.filename === m.filename);
                const isActive = isModelActive(m.filename);

                return (
                  <div
                    key={m.filename}
                    className="flex flex-col justify-between rounded-lg border border-border/60 bg-muted/20 p-3"
                  >
                    <div className="mb-3">
                      <div className="font-semibold text-sm flex items-center gap-2">
                        {m.name}
                        {isActive && (
                          <Badge
                            variant="outline"
                            className="text-[10px] h-5 border-success text-success bg-success/10 px-1"
                          >
                            Active
                          </Badge>
                        )}
                      </div>
                      <div className="text-[10px] text-muted-foreground font-mono mt-1">
                        Size: {m.size} &bull; Template: {m.template}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mt-auto">
                      {isActive ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="w-full gap-2 hover:bg-amber-500/10 hover:text-amber-500 hover:border-amber-500/30 transition-colors"
                          onClick={handleUnload}
                        >
                          <PowerOff size={14} /> Unload
                        </Button>
                      ) : isDownloaded ? (
                        <Button
                          size="sm"
                          variant="default"
                          className="w-full gap-2 bg-primary/20 text-primary hover:bg-primary/30"
                          onClick={() => handleLoad(m.filename, m.template)}
                        >
                          <Play size={14} /> Load Model
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="w-full gap-2"
                          onClick={() => handleDownload(m)}
                          disabled={progress?.is_downloading}
                        >
                          <CloudDownload size={14} /> Download
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Dialog>
      <DialogTrigger render={<Button variant="outline" className="gap-2" />}>
        <Database size={14} />
        Model Manager
      </DialogTrigger>
      <DialogContent className="max-w-4xl sm:max-w-4xl p-0 gap-0 overflow-hidden border-border bg-surface shadow-2xl shadow-black/20 dark:shadow-black/90">
        <DialogHeader className="border-b border-border px-6 py-4 bg-background/80">
          <div className="text-left">
            <DialogTitle className="mt-1 text-lg font-bold text-foreground">Model Manager</DialogTitle>
          </div>
        </DialogHeader>

        <div className="flex-1 max-h-[70vh] overflow-y-auto overflow-x-hidden hide-scrollbar">{renderContent()}</div>
      </DialogContent>
    </Dialog>
  );
}
