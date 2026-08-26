"use client";

import { useMemo, useRef, useState, useEffect } from "react";
import useSWR from "swr";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  CheckCircle2,
  Clock,
  Loader2,
  MoreHorizontal,
  PlayCircle,
  RefreshCw,
  Server,
  XCircle,
  Play,
  RotateCcw,
  SkipForward,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getLayerTasks, getLayer, retryTask, skipTask, formatApiError, requeueFailedLayerTasks, type TaskList } from "@/services/api";
import type { RenderJob } from "@/types/dashboard";
import type { WorkerNode, WorkerPool } from "@/services/api";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { TaskLogsDialog } from "./TaskLogsDialog";
import { LayerInfoDialog } from "./LayerInfoDialog";
import { FileText } from "lucide-react";

export interface TaskDetailPanelProps {
  selectedJobId: string | null;
  selectedLayerId: string | null;
  jobs: RenderJob[];
  nodes: WorkerNode[];
  pools: WorkerPool[];
  onSelectLayer: (jobId: string, layerId: string) => void;
}

type TaskTabFilter = "ALL" | "RUNNING" | "FAILED" | "READY";

function getTaskStateConfig(state: string) {
  switch (state) {
    case "SUCCEEDED": return { icon: CheckCircle2, variant: "success", label: "Done" };
    case "FAILED": return { icon: XCircle, variant: "destructive", label: "Failed" };
    case "RUNNING": return { icon: PlayCircle, variant: "info", label: "Run" };
    case "READY": return { icon: Clock, variant: "warning", label: "Ready" };
    case "WAITING": return { icon: MoreHorizontal, variant: "secondary", label: "Wait" };
    case "SKIPPED": return { icon: SkipForward, variant: "secondary", label: "Skip" };
    default: return { icon: Clock, variant: "secondary", label: state };
  }
}

function formatDuration(startedAt: string | null, stoppedAt: string | null) {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = stoppedAt ? new Date(stoppedAt).getTime() : Date.now();
  const diffSec = Math.floor((end - start) / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  const m = Math.floor(diffSec / 60);
  const s = diffSec % 60;
  return `${m}m ${s}s`;
}

export function TaskDetailPanel({
  selectedJobId,
  selectedLayerId,
  jobs,
  nodes,
  pools,
  onSelectLayer,
}: TaskDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<TaskTabFilter>("ALL");
  const [isRequeuing, setIsRequeuing] = useState(false);
  const [actionTaskId, setActionTaskId] = useState<string | null>(null);

  const [logDialogOpen, setLogDialogOpen] = useState(false);
  const [logTaskId, setLogTaskId] = useState<string | null>(null);
  const [logTaskName, setLogTaskName] = useState<string | null>(null);

  const [infoDialogOpen, setInfoDialogOpen] = useState(false);

  const openTaskLogs = (taskId: string, taskName: string) => {
    setLogTaskId(taskId);
    setLogTaskName(taskName);
    setLogDialogOpen(true);
  };

  const parentContainerRef = useRef<HTMLDivElement>(null);

  const selectedJob = useMemo(() => jobs.find(j => j.id === selectedJobId), [jobs, selectedJobId]);

  // Fetch tasks for selected layer
  const { data: allTasks = [], isValidating, mutate } = useSWR<TaskList[]>(
    selectedJobId && selectedLayerId ? `/api/jobs/${selectedJobId}/layers/${selectedLayerId}/tasks/` : null,
    () => getLayerTasks(selectedJobId!, selectedLayerId!),
    { refreshInterval: 10000, revalidateOnFocus: true }
  );

  // Fetch layer details
  const { data: layerDetail } = useSWR(
    selectedJobId && selectedLayerId ? `/api/jobs/${selectedJobId}/layers/${selectedLayerId}/detail/` : null,
    () => getLayer(selectedJobId!, selectedLayerId!),
    { refreshInterval: 10000, revalidateOnFocus: true }
  );

  const filteredTasks = useMemo(() => {
    if (activeTab === "ALL") return allTasks;
    if (activeTab === "RUNNING") return allTasks.filter(t => t.state === "RUNNING");
    if (activeTab === "FAILED") return allTasks.filter(t => t.state === "FAILED");
    if (activeTab === "READY") return allTasks.filter(t => t.state === "READY" || t.state === "WAITING");
    return allTasks;
  }, [allTasks, activeTab]);

  const commonPrefix = useMemo(() => {
    if (allTasks.length === 0) return "";
    let prefix = allTasks[0].name;
    for (let i = 1; i < allTasks.length; i++) {
      while (allTasks[i].name.indexOf(prefix) !== 0) {
        prefix = prefix.substring(0, prefix.length - 1);
        if (prefix === "") return "";
      }
    }
    const lastSep = Math.max(prefix.lastIndexOf('_'), prefix.lastIndexOf('-'), prefix.lastIndexOf(' '));
    if (lastSep !== -1) {
      return prefix.substring(0, lastSep + 1);
    }
    return prefix.replace(/\d+$/, '');
  }, [allTasks]);

  const rowVirtualizer = useVirtualizer({
    count: filteredTasks.length,
    getScrollElement: () => parentContainerRef.current,
    estimateSize: () => 36,
    overscan: 5,
  });

  const handleRetry = async (taskId: string) => {
    setActionTaskId(taskId);
    try {
      await retryTask(taskId);
      toast.success("Task retried");
      void mutate();
    } catch (error) {
      toast.error("Retry failed", { description: formatApiError(error) });
    } finally {
      setActionTaskId(null);
    }
  };

  const handleSkip = async (taskId: string) => {
    setActionTaskId(taskId);
    try {
      await skipTask(taskId);
      toast.success("Task skipped");
      void mutate();
    } catch (error) {
      toast.error("Skip failed", { description: formatApiError(error) });
    } finally {
      setActionTaskId(null);
    }
  };

  const handleRequeueAll = async () => {
    if (!selectedJobId || !selectedLayerId) return;
    setIsRequeuing(true);
    try {
      const res = await requeueFailedLayerTasks(selectedJobId, selectedLayerId);
      toast.success("Requeued tasks", { description: `Requeued ${res.requeued_count} failed task(s).` });
      void mutate();
    } catch (error) {
      toast.error("Requeue failed", { description: formatApiError(error) });
    } finally {
      setIsRequeuing(false);
    }
  };

  if (!selectedJobId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8 bg-surface-deep text-center">
        <Server size={32} className="mb-4 opacity-30" />
        <h3 className="text-sm font-bold text-foreground">No Job Selected</h3>
        <p className="text-xs mt-1 max-w-sm">Select a job from the queue on the left to inspect its layers and active tasks.</p>
      </div>
    );
  }

  if (selectedJobId && !selectedLayerId) {
    return (
      <div className="flex-1 flex flex-col min-h-0 min-w-0 bg-surface-deep h-full overflow-hidden">
        {/* Header */}
        <div className="h-10 px-3 bg-muted/40 border-b border-border/50 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2 text-sm">
            <h2 className="font-bold text-foreground">Job Details: {selectedJob?.displayId}</h2>
          </div>
          <div className="text-[11px] font-mono text-muted-foreground bg-muted/30 px-2 py-0.5 rounded border border-border/50">
            ID: {selectedJob?.id?.split('-')[0]}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto bg-surface-deep p-6">
          <div className="max-w-2xl w-full mx-auto">
            <div className="flex flex-col gap-10 text-xs">
              <div>
                <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-4 opacity-80">General Information</h3>
                <div className="grid grid-cols-2 gap-y-3 gap-x-8 font-mono">
                  <div><span className="text-muted-foreground opacity-70">Name:</span> <span className="text-foreground font-bold ml-2">{selectedJob?.displayId}</span></div>
                  <div><span className="text-muted-foreground opacity-70">User:</span> <span className="text-foreground ml-2">{selectedJob?.user || "system"}</span></div>
                  <div><span className="text-muted-foreground opacity-70">Project:</span> <span className="text-foreground ml-2">{selectedJob?.project || "N/A"}</span></div>
                  <div><span className="text-muted-foreground opacity-70">Department:</span> <span className="text-foreground ml-2">{selectedJob?.department || "N/A"}</span></div>
                  <div><span className="text-muted-foreground opacity-70">Priority:</span> <span className="text-foreground ml-2">{selectedJob?.priority}</span></div>
                  <div><span className="text-muted-foreground opacity-70">Pools:</span> <span className="text-foreground ml-2">{selectedJob?.included_pools?.map(poolId => pools.find(p => p.id === poolId)?.name || poolId).join(", ") || "Any"}</span></div>
                </div>
              </div>
            
            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-4 opacity-80">Status & Progress</h3>
              <div className="grid grid-cols-2 gap-y-3 gap-x-8 font-mono">
                <div><span className="text-muted-foreground opacity-70">State:</span> <span className="text-foreground ml-2 font-bold">{selectedJob?.status}</span></div>
                <div><span className="text-muted-foreground opacity-70">Progress:</span> <span className="text-foreground ml-2">{Math.round(((selectedJob?.succeeded_tasks || 0) + (selectedJob?.skipped_tasks || 0)) / Math.max(1, selectedJob?.total_tasks || 1) * 100)}%</span></div>
                <div><span className="text-muted-foreground opacity-70">Total Tasks:</span> <span className="text-foreground ml-2">{selectedJob?.total_tasks}</span></div>
                <div><span className="text-muted-foreground opacity-70">Completed:</span> <span className="text-success ml-2">{selectedJob?.succeeded_tasks}</span></div>
                <div><span className="text-muted-foreground opacity-70">Running:</span> <span className="text-info ml-2">{selectedJob?.running_tasks}</span></div>
                <div><span className="text-muted-foreground opacity-70">Failed:</span> <span className="text-destructive ml-2">{selectedJob?.failed_tasks}</span></div>
              </div>
            </div>

            <div>
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-4 opacity-80">Timeline</h3>
              <div className="flex flex-col gap-3 font-mono">
                <div><span className="text-muted-foreground opacity-70 w-24 inline-block">Submitted:</span> <span className="text-foreground">{selectedJob?.created_at ? new Date(selectedJob.created_at).toLocaleString() : "N/A"}</span></div>
                <div><span className="text-muted-foreground opacity-70 w-24 inline-block">Started:</span> <span className="text-foreground">{selectedJob?.started_at ? new Date(selectedJob.started_at).toLocaleString() : "N/A"}</span></div>
                <div><span className="text-muted-foreground opacity-70 w-24 inline-block">Finished:</span> <span className="text-foreground">{selectedJob?.finished_at ? new Date(selectedJob.finished_at).toLocaleString() : "N/A"}</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    );
  }

  const failedCount = allTasks.filter(t => t.state === "FAILED").length;
  const runningCount = allTasks.filter(t => t.state === "RUNNING").length;
  const readyCount = allTasks.filter(t => t.state === "READY" || t.state === "WAITING").length;

  return (
    <div className="flex-1 flex flex-col min-h-0 min-w-0 bg-surface-deep h-full overflow-hidden">
      {/* Header */}
      <div className="bg-muted/40 border-b border-border/50 flex flex-col shrink-0">
        <div className="min-h-10 px-3 py-2 flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1.5 min-w-0">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-semibold text-muted-foreground shrink-0">{selectedJob?.displayId}</span>
              <span className="text-muted-foreground shrink-0">›</span>
              <span className="font-bold text-foreground truncate">{layerDetail?.name || "Task List"}</span>
              {layerDetail && (
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-6 w-6 ml-1 text-muted-foreground hover:text-foreground shrink-0" 
                  onClick={() => setInfoDialogOpen(true)}
                  title="View Layer Info"
                >
                  <FileText className="size-3.5" />
                </Button>
              )}
              {isValidating && <RefreshCw size={12} className="text-muted-foreground animate-spin ml-2 shrink-0" />}
            </div>
          </div>
          {failedCount > 0 && (
            <Button 
              size="sm" 
              variant="outline" 
              className="h-7 text-xs border-amber-500/40 bg-amber-500/10 text-amber-500 hover:bg-amber-500/20"
              onClick={handleRequeueAll}
              disabled={isRequeuing}
            >
              <RotateCcw size={12} className={cn("mr-1.5", isRequeuing && "animate-spin")} />
              Requeue {failedCount} Failed
            </Button>
          )}
        </div>
        
        <div className="px-3 pb-2 flex items-center justify-between mt-1">
          <div className="flex flex-wrap gap-1">
            {(["ALL", "RUNNING", "FAILED", "READY"] as TaskTabFilter[]).map((tab) => {
              const isActive = activeTab === tab;
              let count = allTasks.length;
              if (tab === "RUNNING") count = runningCount;
              if (tab === "FAILED") count = failedCount;
              if (tab === "READY") count = readyCount;
              
              return (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "px-2 py-1 rounded text-[11px] font-mono font-medium transition-colors flex items-center gap-1 cursor-pointer",
                    isActive ? "bg-primary text-primary-foreground" : "bg-muted/50 text-muted-foreground hover:bg-muted"
                  )}
                >
                  {tab} <span className="opacity-70">{count}</span>
                </button>
              )
            })}
          </div>
          <div className="text-[11px] font-mono text-muted-foreground">
            Showing {filteredTasks.length} tasks
          </div>
        </div>
      </div>

      {/* Table Header (Fixed) */}
      <div className="grid grid-cols-[minmax(80px,1fr)_96px_minmax(120px,1fr)_96px_64px] items-center gap-2 p-1.5 border-b border-border/50 bg-muted/40 text-[11px] font-bold uppercase tracking-wider text-foreground pr-6">
        <div className="min-w-0 pl-3">Task</div>
        <div className="min-w-0 text-center">State</div>
        <div className="min-w-0 text-center">Worker</div>
        <div className="min-w-0 text-center">Time</div>
        <div className="min-w-0 text-right pr-2">Action</div>
      </div>

      {/* Virtualized Task List */}
      <div 
        ref={parentContainerRef} 
        className="flex-1 overflow-auto no-scrollbar relative font-mono text-xs"
      >
        <div
          style={{
            height: `${rowVirtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const task = filteredTasks[virtualRow.index];
            const cfg = getTaskStateConfig(task.state);
            const StateIcon = cfg.icon;
            const isActioning = actionTaskId === task.id;

            const workerDisplay = task.worker_name || "—";

            let displayTaskName = task.name;
            if (commonPrefix && displayTaskName.startsWith(commonPrefix)) {
              displayTaskName = displayTaskName.slice(commonPrefix.length).replace(/^[-_ ]+/, "");
              if (!displayTaskName) displayTaskName = task.name;
            }

            return (
              <div
                key={task.id}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="grid grid-cols-[minmax(80px,1fr)_96px_minmax(120px,1fr)_96px_64px] items-center gap-2 p-1.5 border-b border-border/30 hover:bg-muted/30 transition-colors group cursor-pointer pr-6"
                onClick={() => openTaskLogs(task.id, task.name)}
              >
                <div className="min-w-0 pl-3 font-semibold text-[11px]">{displayTaskName}</div>
                <div className="min-w-0 flex justify-center">
                  <span className={cn("text-[10px] font-black uppercase tracking-wider", {
                    "text-success": cfg.variant === "success",
                    "text-destructive": cfg.variant === "destructive",
                    "text-info animate-pulse": cfg.variant === "info" || task.state === "RUNNING",
                    "text-warning": cfg.variant === "warning",
                    "text-muted-foreground": cfg.variant === "secondary" || cfg.variant === "outline" || !cfg.variant
                  })}>
                    {cfg.label}
                  </span>
                </div>
                <div className="min-w-0 text-center truncate text-muted-foreground text-[11px]">
                  {workerDisplay}
                </div>
                <div className="min-w-0 text-center tabular-nums text-muted-foreground opacity-80 text-[11px]">
                  {formatDuration(task.started_at, task.stopped_at)}
                </div>
                <div className="min-w-0 flex justify-end gap-1 pr-2 transition-opacity">
                  {task.state === "FAILED" ? (
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:bg-destructive/10" disabled={isActioning} onClick={(e) => { e.stopPropagation(); handleRetry(task.id); }}>
                      <RotateCcw size={12} className={isActioning ? "animate-spin" : ""} />
                    </Button>
                  ) : (task.state === "READY" || task.state === "WAITING") ? (
                    <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:bg-muted" disabled={isActioning} onClick={(e) => { e.stopPropagation(); handleSkip(task.id); }}>
                      <SkipForward size={12} className={isActioning ? "animate-spin" : ""} />
                    </Button>
                  ) : (
                    <div className="h-6 w-6" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {filteredTasks.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs">
            No tasks match the selected filter.
          </div>
        )}
      </div>

      <TaskLogsDialog
        isOpen={logDialogOpen}
        onClose={() => setLogDialogOpen(false)}
        taskId={logTaskId}
        taskName={logTaskName}
      />
      <LayerInfoDialog 
        jobId={selectedJobId} 
        layerId={selectedLayerId} 
        isOpen={infoDialogOpen} 
        onClose={() => setInfoDialogOpen(false)} 
      />
    </div>
  );
}

function LayersIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 12 12 17 22 12" />
      <polyline points="2 17 12 22 22 17" />
    </svg>
  )
}
