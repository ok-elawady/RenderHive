"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  RefreshCw,
  Settings2,
  LayoutList,
  LayoutGrid,
  CheckCircle2,
  Clock,
  Trash2,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  formatApiError,
  getLayer,
  getLayerTasks,
  requeueFailedLayerTasks,
  getJobDependencies,
  deleteDependency,
  type Dependency,
  type TaskList,
  type TaskStateFilter,
  type LayerDetail,
} from "@/services/api";
import { DependencyFlow } from "@/components/dashboard/DependencyFlow";
import TaskLogViewerDialog from "@/components/jobs/TaskLogViewerDialog";
import { Terminal } from "lucide-react";


const taskStates: Array<TaskStateFilter | "ALL"> = [
  "ALL",
  "READY",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "SKIPPED",
  "WAITING",
];

function getTaskClasses(state: TaskList["state"]): string {
  if (state === "FAILED") {
    return "border-destructive/60 bg-destructive/20 text-destructive shadow-sm shadow-destructive/20";
  }
  if (state === "RUNNING") {
    return "border-warning/40 bg-warning/15 text-warning animate-pulse shadow-sm shadow-warning/10";
  }
  if (state === "SUCCEEDED") {
    return "border-success/30 bg-success/10 text-success shadow-sm shadow-success/5";
  }
  if (state === "SKIPPED") {
    return "border-sky-400/40 bg-sky-500/10 text-sky-500 shadow-sm shadow-sky-500/5";
  }
  if (state === "READY") {
    return "border-border bg-muted/30 text-foreground";
  }
  return "border-input bg-input/20 text-muted-foreground";
}

export default function LayerInspectorPage() {
  const params = useParams<{ jobId: string; layerId: string }>();
  const [layer, setLayer] = useState<LayerDetail | null>(null);
  const [tasks, setTasks] = useState<TaskList[]>([]);
  const [stateFilter, setStateFilter] = useState<TaskStateFilter | "ALL">("ALL");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRequeuingFailed, setIsRequeuingFailed] = useState<boolean>(false);
  const [selectedTaskForLog, setSelectedTaskForLog] = useState<{ id: string; name: string; state?: TaskList["state"] } | null>(null);

  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [isDeletingDependency, setIsDeletingDependency] = useState<string | null>(null);
  const [blockerToDelete, setBlockerToDelete] = useState<Dependency | null>(null);

  const blockers = useMemo(() => {
    return dependencies.filter((dep) => dep.dep_layer === layer?.id);
  }, [dependencies, layer?.id]);

  const [blockersPage, setBlockersPage] = useState<number>(1);
  const BLOCKERS_PAGE_SIZE = 10;
  
  const paginatedBlockers = useMemo(() => {
    return blockers.slice((blockersPage - 1) * BLOCKERS_PAGE_SIZE, blockersPage * BLOCKERS_PAGE_SIZE);
  }, [blockers, blockersPage]);

  const failedTaskCount = useMemo(() => tasks.filter((t) => t.state === "FAILED").length, [tasks]);

  const visibleTasks = useMemo(() => {
    const filtered = stateFilter === "ALL" ? tasks : tasks.filter((task) => task.state === stateFilter);
    return [...filtered].sort((a, b) => {
      if (a.frame_start !== b.frame_start) {
        return a.frame_start - b.frame_start;
      }
      if (a.frame_end !== b.frame_end) {
        return a.frame_end - b.frame_end;
      }
      return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" });
    });
  }, [tasks, stateFilter]);

  const refreshTasks = useCallback(async (): Promise<void> => {
    const taskData = await getLayerTasks(params.jobId, params.layerId);
    setTasks(taskData);
  }, [params.jobId, params.layerId]);

  const loadLayer = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const [layerData, taskData, depsData] = await Promise.all([
        getLayer(params.jobId, params.layerId),
        getLayerTasks(params.jobId, params.layerId),
        getJobDependencies(params.jobId),
      ]);
      setLayer(layerData);
      setTasks(taskData);
      setDependencies(depsData);
    } catch (error) {
      toast.error("Unable to load layer tasks", {
        description: formatApiError(error),
      });
    } finally {
      setIsLoading(false);
    }
  }, [params.jobId, params.layerId]);

  useEffect(() => {
    void loadLayer();
    const interval = window.setInterval(() => {
      void refreshTasks();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [loadLayer, refreshTasks]);

  const handleRequeueFailed = async (): Promise<void> => {
    setIsRequeuingFailed(true);
    try {
      const res = await requeueFailedLayerTasks(params.jobId, params.layerId);
      toast.success("Failed tasks requeued", {
        description: `Requeued ${res.requeued_count} failed task(s) in this layer.`,
      });
      await refreshTasks();
    } catch (error) {
      toast.error("Requeue failed", { description: formatApiError(error) });
    } finally {
      setIsRequeuingFailed(false);
    }
  };

  const handleDeleteBlocker = async (depId: string): Promise<void> => {
    setIsDeletingDependency(depId);
    try {
      await deleteDependency(depId);
      setDependencies((current) => current.filter((d) => d.id !== depId));
      toast.success("Blocker removed");
    } catch (error) {
      toast.error("Failed to remove blocker", { description: formatApiError(error) });
    } finally {
      setIsDeletingDependency(null);
    }
  };

  return (
    <div className="flex h-full flex-col bg-background font-sans text-foreground">
      <PageHeader
        title={layer?.name ?? "Layer Inspector"}
        description={layer ? `${layer.layer_type} • Frames ${layer.frame_range}` : "Fetching tasks..."}
        backTo={`/jobs/${params.jobId}`}
      >
        <Button variant="outline" onClick={() => void loadLayer()} className="gap-2">
          <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
          Refresh
        </Button>
        {failedTaskCount > 0 && (
          <Button
            variant="outline"
            onClick={() => void handleRequeueFailed()}
            disabled={isRequeuingFailed}
            className="gap-2 border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 hover:text-amber-200"
          >
            <RefreshCw size={14} className={isRequeuingFailed ? "animate-spin" : ""} />
            Requeue Failed ({failedTaskCount})
          </Button>
        )}
      </PageHeader>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="space-y-6">
          <div className="flex flex-col gap-6">
            {/* Layer Configuration Card */}
            <Card className="border-border">
              <CardHeader className="pb-3 border-b border-border/50">
                <CardTitle className="flex items-center gap-2 text-sm font-bold">
                  <Settings2 size={16} className="text-primary" />
                  Layer Configuration
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 grid grid-cols-2 gap-y-5 gap-x-6 text-sm">
                <div>
                  <div className="text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-1.5">
                    Command
                  </div>
                  <div className="font-medium break-all whitespace-pre-wrap leading-relaxed">
                    {layer?.command || "—"}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-1.5">
                    Layer Type
                  </div>
                  <div className="font-medium">
                    <Badge variant="secondary" className="rounded-sm px-2 py-0.5 text-xs font-normal">
                      {layer?.layer_type ?? "—"}
                    </Badge>
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-1.5">
                    Chunk Size
                  </div>
                  <div className="font-medium">{layer?.chunk_size ?? "—"} frames</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs font-semibold uppercase tracking-wider mb-1.5">
                    Min Hardware
                  </div>
                  <div className="font-medium">
                    {layer?.min_cores}C / {layer?.min_memory_mb}MB / {layer?.min_gpus}G
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border p-0 gap-0">
              <CardHeader className="p-4 pb-3 border-b border-border/50">
                <CardTitle className="flex items-center gap-2 text-sm font-bold">
                  <LayoutList size={16} className="text-destructive" />
                  Active Blockers{" "}
                  {blockers.length > 0 && (
                    <Badge variant="destructive" className="text-xs">
                      {blockers.length}
                    </Badge>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent variant="flush" className="flex flex-col">
                <Table containerClassName="max-h-[220px] overflow-y-auto">
                  <TableHeader className="sticky top-0 z-10 shadow-sm bg-card">
                    <TableRow className="hover:bg-transparent bg-muted/30">
                      <TableHead className="pl-6 font-semibold text-xs">Depends On</TableHead>
                      <TableHead className="font-semibold text-center text-xs">Type</TableHead>
                      <TableHead className="font-semibold text-center text-xs">Status</TableHead>
                      <TableHead className="pr-6 font-semibold text-xs text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {blockers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="h-24 text-center text-xs text-muted-foreground">
                          No active blockers for this layer.
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedBlockers.map((blocker) => (
                        <TableRow key={blocker.id} className="hover:bg-muted/40 transition-colors group">
                          <TableCell className="pl-6 text-xs font-medium text-foreground py-2.5">
                            <DependencyFlow dep={blocker} currentJobId={params.jobId} isInbound={true} />
                          </TableCell>
                          <TableCell className="text-center text-[11px] font-medium text-muted-foreground tracking-wide uppercase">
                            {blocker.type === "TASK_ON_TASK" ? "Task → Task" : "Layer → Layer"}
                          </TableCell>
                          <TableCell className="text-center">
                            {blocker.is_satisfied ? (
                              <Badge
                                variant="secondary"
                                className="bg-success/15 text-success hover:bg-success/20 gap-1 pr-2"
                              >
                                <CheckCircle2 className="size-3" /> Satisfied
                              </Badge>
                            ) : (
                              <Badge
                                variant="secondary"
                                className="bg-warning/15 text-warning hover:bg-warning/20 gap-1 pr-2"
                              >
                                <Clock className="size-3" /> Pending
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell className="pr-6 text-right py-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setBlockerToDelete(blocker)}
                              disabled={isDeletingDependency === blocker.id}
                              aria-label="Remove blocker"
                              className="h-7 w-7 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 size={14} />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
                {blockers.length > BLOCKERS_PAGE_SIZE && (
                  <div className="flex items-center justify-end space-x-2 py-2 px-4 border-t border-border/50 bg-muted/10">
                    <span className="text-xs text-muted-foreground mr-2">
                      Page {blockersPage} of {Math.ceil(blockers.length / BLOCKERS_PAGE_SIZE)}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 w-7 p-0"
                      disabled={blockersPage === 1}
                      onClick={() => setBlockersPage((p) => Math.max(1, p - 1))}
                      aria-label="Previous blockers page"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 w-7 p-0"
                      disabled={blockersPage * BLOCKERS_PAGE_SIZE >= blockers.length}
                      onClick={() => setBlockersPage((p) => p + 1)}
                      aria-label="Next blockers page"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="border-border p-0 gap-0">
            <Tabs
              value={stateFilter}
              onValueChange={(value) => setStateFilter(value as TaskStateFilter | "ALL")}
            >
              <CardHeader className="p-4 pb-3 mb-0 border-b border-border/50">
                <CardTitle className="flex items-center gap-2 text-sm font-bold">
                  <LayoutGrid size={16} className="text-primary" />
                  Task Grid
                </CardTitle>
              </CardHeader>
              <TabsList>
                {taskStates.map((state) => {
                  const count = state === "ALL" ? tasks.length : tasks.filter((t) => t.state === state).length;
                  return (
                    <TabsTrigger key={state} value={state} className="text-xs px-3 py-1 gap-2">
                      {state}
                      {count > 0 && (
                        <Badge
                          variant={state === "FAILED" ? "destructive" : "secondary"}
                          className={`px-2 py-0.5 text-xs rounded-full h-5 min-w-5 justify-center font-medium ${
                            state === "FAILED" ? "bg-destructive text-destructive-foreground" : ""
                          }`}
                        >
                          {count}
                        </Badge>
                      )}
                    </TabsTrigger>
                  );
                })}
              </TabsList>
              <CardContent className="p-4 flex flex-col gap-4">
                <TabsContent value={stateFilter} className="m-0 border-none p-0 outline-none">
                  {isLoading ? (
                    <div className="flex h-56 items-center justify-center text-muted-foreground">Loading tasks...</div>
                  ) : visibleTasks.length === 0 ? (
                    <div className="flex h-24 flex-col items-center justify-center rounded-lg border-2 border-dashed border-border/50 bg-muted/5 text-sm text-muted-foreground">
                      <LayoutGrid className="mb-2 size-8 opacity-20" />
                      No tasks found {stateFilter}
                    </div>
                  ) : (
                    <div className="grid grid-cols-8 gap-2.5 sm:grid-cols-10 md:grid-cols-12 lg:grid-cols-[repeat(16,minmax(0,1fr))] xl:grid-cols-[repeat(20,minmax(0,1fr))]">
                      {visibleTasks.map((task) => (
                        <div
                          key={task.id}
                          title={`${task.name} / ${task.state} (Click to inspect log & actions)`}
                          aria-label={`Task ${task.name}: ${task.state}, frames ${task.frame_start} to ${task.frame_end}`}
                          tabIndex={0}
                          onClick={() => setSelectedTaskForLog({ id: task.id, name: task.name, state: task.state })}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelectedTaskForLog({ id: task.id, name: task.name, state: task.state });
                            }
                          }}
                          className={`group relative aspect-square overflow-hidden rounded-md border text-xs font-semibold cursor-pointer transition-all hover:scale-[1.06] hover:ring-2 hover:ring-primary/70 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none flex items-center justify-center select-none ${getTaskClasses(task.state)}`}
                        >
                          <span>
                            {task.frame_start + (task.frame_start !== task.frame_end ? "-" + task.frame_end : "")}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="mt-5 flex flex-wrap gap-4 text-xs font-medium text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <i className="size-2.5 rounded-sm bg-muted/50 border border-border" /> READY
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <i className="size-2.5 rounded-sm bg-warning/20 border border-warning/40" /> RUNNING
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <i className="size-2.5 rounded-sm bg-success/15 border border-success/30" /> SUCCEEDED
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <i className="size-2.5 rounded-sm bg-destructive/20 border border-destructive/50" /> FAILED
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <i className="size-2.5 rounded-sm bg-sky-500/15 border border-sky-400/40" /> SKIPPED
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/50 bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <Terminal size={13} className="text-primary" />
                      <span>Click any task tile to inspect stdout/stderr execution logs, diagnostics, or trigger Requeue / Skip.</span>
                    </div>
                  </div>
                </TabsContent>
              </CardContent>
            </Tabs>
          </Card>
        </div>
      </div>

      <TaskLogViewerDialog
        taskId={selectedTaskForLog?.id || null}
        taskName={selectedTaskForLog?.name}
        taskState={selectedTaskForLog?.state}
        isOpen={Boolean(selectedTaskForLog)}
        onOpenChange={(open) => {
          if (!open) setSelectedTaskForLog(null);
        }}
        onTaskUpdated={() => {
          void refreshTasks();
          if (selectedTaskForLog) {
            setSelectedTaskForLog((prev) => (prev ? { ...prev, state: "READY" } : null));
          }
        }}
      />

      {/* Blocker Deletion Confirmation Dialog */}
      <ConfirmDialog
        open={!!blockerToDelete}
        onOpenChange={(open) => !open && setBlockerToDelete(null)}
        variant="destructive"
        title="Remove Blocker Dependency"
        description="Are you sure you want to remove this dependency blocker? This will allow blocked tasks to proceed immediately. This action cannot be undone."
        confirmText="Remove Blocker"
        isLoading={Boolean(blockerToDelete && isDeletingDependency === blockerToDelete.id)}
        onConfirm={async () => {
          if (blockerToDelete) {
            await handleDeleteBlocker(blockerToDelete.id);
            setBlockerToDelete(null);
          }
        }}
      />
    </div>
  );
}

