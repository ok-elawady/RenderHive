"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  Cpu,
  FileText,
  HardDrive,
  ImageIcon,
  ListTree,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Server,
  SkipForward,
  Terminal,
  WrapText,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchTaskExecutionLogById,
  fetchTaskExecutionLogLatest,
  fetchTaskExecutionLogs,
  retryTask,
  skipTask,
  formatApiError,
} from "@/services/api";
import type { TaskLogList } from "@/types/dashboard";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type LogTab = "full" | "error" | "diagnostics";

interface TaskLogViewerDialogProps {
  taskId: string | null;
  taskName?: string;
  taskState?: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onTaskUpdated?: () => void;
}

export default function TaskLogViewerDialog({
  taskId,
  taskName,
  taskState,
  isOpen,
  onOpenChange,
  onTaskUpdated,
}: TaskLogViewerDialogProps) {
  const [activeTab, setActiveTab] = useState<LogTab>("full");
  const [wrapLines, setWrapLines] = useState<boolean>(true);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [isRequeuing, setIsRequeuing] = useState<boolean>(false);
  const [isSkipping, setIsSkipping] = useState<boolean>(false);

  const handleRequeue = async () => {
    if (!taskId) return;
    setIsRequeuing(true);
    try {
      await retryTask(taskId);
      toast.success("Task requeued", {
        description: `Task was requeued back into the READY queue.`,
      });
      void mutate();
      onTaskUpdated?.();
    } catch (error) {
      toast.error("Requeue failed", { description: formatApiError(error) });
    } finally {
      setIsRequeuing(false);
    }
  };

  const handleSkip = async () => {
    if (!taskId) return;
    setIsSkipping(true);
    try {
      await skipTask(taskId);
      toast.success("Task skipped", {
        description: `Task was marked as SKIPPED.`,
      });
      void mutate();
      onTaskUpdated?.();
    } catch (error) {
      toast.error("Skip failed", { description: formatApiError(error) });
    } finally {
      setIsSkipping(false);
    }
  };

  // Fetch all attempts for this task
  const { data: allAttempts = [] } = useSWR<TaskLogList[]>(
    taskId && isOpen ? [`/api/telemetry/tasks/logs/`, taskId] : null,
    () => (taskId ? fetchTaskExecutionLogs(taskId) : Promise.resolve([])),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    }
  );

  const activeLogId = selectedLogId || (allAttempts.length > 0 ? allAttempts[0].id : null);

  const {
    data: logDetail,
    isLoading,
    error,
    mutate,
    isValidating,
  } = useSWR(
    taskId && isOpen ? [`/api/telemetry/tasks/logs/detail/`, taskId, activeLogId] : null,
    () => {
      if (activeLogId) {
        return fetchTaskExecutionLogById(activeLogId);
      }
      return taskId ? fetchTaskExecutionLogLatest(taskId) : null;
    },
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    }
  );

  const handleCopyLog = async () => {
    const textToCopy =
      activeTab === "error" && logDetail?.error_tail
        ? logDetail.error_tail
        : logDetail?.log_output;

    if (!textToCopy) return;
    try {
      await navigator.clipboard.writeText(textToCopy);
      toast.success(
        activeTab === "error" ? "Error tail copied to clipboard" : "Task log copied to clipboard"
      );
    } catch {
      toast.error("Failed to copy log to clipboard");
    }
  };

  const isSuccess = logDetail?.exit_status === 0;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl sm:max-w-4xl max-h-[88vh] flex flex-col p-0 gap-0 border-border bg-surface shadow-2xl overflow-hidden font-mono">
        {/* Card Header (Clean, standard with close X alone on right) */}
        <DialogHeader className="border-b border-border/50 px-6 py-4 bg-surface flex flex-row items-center justify-between space-y-0 shrink-0 pr-12">
          <div className="text-left space-y-1 min-w-0 flex-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <Terminal className="size-4 text-primary shrink-0" />
              <DialogTitle className="text-base font-bold text-foreground truncate">
                Task Log: {taskName || logDetail?.task_name || taskId}
              </DialogTitle>
              {taskState ? (
                <Badge
                  variant={
                    taskState === "FAILED"
                      ? "destructive"
                      : taskState === "SUCCEEDED"
                      ? "outline"
                      : "secondary"
                  }
                  className={`text-[10px] font-mono px-2 py-0.5 shrink-0 ${
                    taskState === "FAILED"
                      ? "border-destructive/40 text-destructive bg-destructive/10"
                      : taskState === "SUCCEEDED"
                      ? "border-success/40 text-success bg-success/10"
                      : taskState === "RUNNING"
                      ? "border-warning/40 text-warning bg-warning/10 animate-pulse"
                      : taskState === "SKIPPED"
                      ? "border-sky-400/40 text-sky-400 bg-sky-500/10"
                      : "border-border text-foreground bg-muted/40"
                  }`}
                >
                  {taskState === "READY" && (
                    <span className="flex items-center gap-1">
                      <Clock className="size-3" /> State: READY
                    </span>
                  )}
                  {taskState === "RUNNING" && (
                    <span className="flex items-center gap-1">
                      <PlayCircle className="size-3" /> State: RUNNING
                    </span>
                  )}
                  {taskState === "SUCCEEDED" && (
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="size-3" /> State: SUCCEEDED
                    </span>
                  )}
                  {taskState === "FAILED" && (
                    <span className="flex items-center gap-1">
                      <XCircle className="size-3" /> State: FAILED (Exit {logDetail?.exit_status ?? 1})
                    </span>
                  )}
                  {taskState === "SKIPPED" && (
                    <span className="flex items-center gap-1">
                      <SkipForward className="size-3" /> State: SKIPPED
                    </span>
                  )}
                  {taskState === "WAITING" && (
                    <span className="flex items-center gap-1">
                      <Clock className="size-3" /> State: WAITING
                    </span>
                  )}
                </Badge>
              ) : logDetail ? (
                <Badge
                  variant={isSuccess ? "outline" : "destructive"}
                  className={`text-[10px] font-mono px-2 py-0.5 shrink-0 ${
                    isSuccess
                      ? "border-success/40 text-success bg-success/10"
                      : "border-destructive/40 text-destructive bg-destructive/10"
                  }`}
                >
                  {isSuccess ? (
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="size-3" /> Exit Code 0 (Success)
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <XCircle className="size-3" /> Exit Code {logDetail.exit_status} (Failed)
                    </span>
                  )}
                </Badge>
              ) : null}
            </div>
            <DialogDescription className="text-xs text-muted-foreground truncate">
              {logDetail?.job_name ? `Job: ${logDetail.job_name}` : "Process stdout, stderr, and hardware diagnostics."}
            </DialogDescription>
          </div>
        </DialogHeader>

        {/* Card Body */}
        <div className="p-6 space-y-4 flex-1 flex flex-col overflow-hidden">
          {taskState === "READY" && (
            <div className="p-2.5 px-3 bg-muted/20 border border-border/70 rounded-lg text-xs font-mono flex items-center justify-between text-muted-foreground shrink-0">
              <div className="flex items-center gap-2">
                <Clock className="size-4 text-primary shrink-0" />
                <span>
                  This task was <strong>requeued</strong> and is currently <strong>READY</strong> in the queue. Viewing execution log from past attempt #{logDetail?.attempt_number || 1}.
                </span>
              </div>
            </div>
          )}
          {/* Multi-attempt Selector if more than 1 attempt exists */}
          {allAttempts.length > 1 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs shrink-0 font-mono">
              <span className="text-muted-foreground font-sans font-medium text-xs flex items-center gap-1 shrink-0">
                <RotateCcw className="size-3.5 text-primary" /> Attempts:
              </span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {allAttempts.map((att) => {
                  const isAttActive = activeLogId === att.id;
                  const isAttSuccess = att.exit_status === 0;
                  return (
                    <button
                      key={att.id}
                      type="button"
                      onClick={() => setSelectedLogId(att.id)}
                      className={cn(
                        "px-2.5 py-1 rounded-md text-xs font-mono font-medium transition-all border inline-flex items-center gap-1.5",
                        isAttActive
                          ? "bg-primary/20 text-primary border-primary/50 font-bold shadow-xs ring-1 ring-primary/30"
                          : "bg-surface-deep text-muted-foreground border-border/70 hover:text-foreground hover:bg-muted/40"
                      )}
                    >
                      <span>Attempt #{att.attempt_number}</span>
                      <Badge
                        variant={isAttSuccess ? "outline" : "destructive"}
                        className={cn(
                          "text-[9px] px-1 py-0 h-4 font-mono font-normal",
                          isAttSuccess
                            ? "border-success/30 text-success bg-success/10"
                            : "border-destructive/30 text-destructive bg-destructive/10"
                        )}
                      >
                        {isAttSuccess ? "Exit 0" : `Exit ${att.exit_status}`}
                      </Badge>
                      {att.worker_hostname && (
                        <span className="text-[10px] text-muted-foreground opacity-70">
                          {att.worker_hostname}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Top Toolbar: Tabs on Left, Log Controls on Right (Strictly single-row) */}
          <div className="flex items-center justify-between gap-3 shrink-0">
            {/* Left: Tab Navigation in Dark Container */}
            <div className="flex items-center gap-1 bg-surface-deep border border-border/80 rounded-lg p-1">
              <Button
                variant={activeTab === "full" ? "default" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("full")}
                className={`h-7 px-3 text-xs font-mono transition-all ${
                  activeTab === "full"
                    ? "bg-primary text-primary-foreground font-bold shadow-xs ring-1 ring-primary/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                }`}
              >
                <FileText className="size-3.5 mr-1.5" />
                Full Log
              </Button>
              <Button
                variant={activeTab === "error" ? "default" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("error")}
                className={`h-7 px-3 text-xs font-mono transition-all ${
                  activeTab === "error"
                    ? "bg-primary text-primary-foreground font-bold shadow-xs ring-1 ring-primary/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                }`}
              >
                <AlertTriangle
                  className={`size-3.5 mr-1.5 ${logDetail?.error_tail && !isSuccess && taskState === "FAILED" ? "text-destructive" : ""}`}
                />
                {taskState === "READY" ? "Past Error Tail" : "Error Tail"}
                {logDetail?.error_tail && !isSuccess && taskState === "FAILED" && (
                  <span className="size-1.5 rounded-full bg-destructive ml-1 animate-pulse" />
                )}
              </Button>
              <Button
                variant={activeTab === "diagnostics" ? "default" : "ghost"}
                size="sm"
                onClick={() => setActiveTab("diagnostics")}
                className={`h-7 px-3 text-xs font-mono transition-all ${
                  activeTab === "diagnostics"
                    ? "bg-primary text-primary-foreground font-bold shadow-xs ring-1 ring-primary/30"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                }`}
              >
                <Cpu className="size-3.5 mr-1.5" />
                Diagnostics
              </Button>
            </div>

            {/* Right: Log Controls (Fixed geometry, never causes row wrapping) */}
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWrapLines(!wrapLines)}
                disabled={activeTab === "diagnostics"}
                className={`h-7.5 px-2.5 text-xs border-border bg-surface-deep hover:bg-muted transition-all ${
                  wrapLines && activeTab !== "diagnostics" ? "bg-primary/15 text-primary border-primary/40 font-semibold" : ""
                } ${activeTab === "diagnostics" ? "opacity-40 cursor-not-allowed" : ""}`}
                title="Toggle line wrapping"
              >
                <WrapText className="size-3.5 mr-1.5" /> Wrap
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleCopyLog}
                disabled={activeTab === "diagnostics" || (!logDetail?.log_output && !logDetail?.error_tail)}
                className={`h-7.5 px-3 text-xs bg-primary text-primary-foreground font-bold ${
                  activeTab === "diagnostics" ? "opacity-40 cursor-not-allowed" : ""
                }`}
              >
                <Copy className="size-3.5 mr-1.5" /> Copy Log
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void mutate()}
                disabled={isValidating}
                className="h-7.5 w-7.5 p-0 text-xs border-border bg-surface-deep hover:bg-muted"
                title="Refresh log"
              >
                <RefreshCw className={`size-3.5 ${isValidating ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>

          {/* Quick Metrics Strip */}
          {logDetail && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-surface-deep rounded-xl border border-input text-xs shrink-0 font-mono">
              <div className="flex items-center gap-2.5">
                <Clock className="size-4 text-muted-foreground shrink-0" />
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Duration</div>
                  <div className="font-bold text-foreground">{logDetail.duration_seconds.toFixed(1)}s</div>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <HardDrive className="size-4 text-primary shrink-0" />
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Peak RAM</div>
                  <div className="font-bold text-foreground">
                    {logDetail.peak_memory_mb ? `${logDetail.peak_memory_mb} MB` : "N/A"}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <Server className="size-4 text-info shrink-0" />
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Worker Node</div>
                  <div className="font-bold text-foreground truncate max-w-[140px]" title={logDetail.worker_hostname}>
                    {logDetail.worker_hostname || "Unknown"}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2.5">
                <Cpu className="size-4 text-warning shrink-0" />
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Attempt</div>
                  <div className="font-bold text-foreground">
                    {logDetail.attempt_number ? `#${logDetail.attempt_number}` : "#1"}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Darker Inner Card for Log & Diagnostics Content */}
          <div className="flex-1 rounded-xl border border-input bg-surface-deep overflow-hidden flex flex-col relative min-h-[300px]">
            {isLoading ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                <RefreshCw className="size-6 animate-spin text-primary opacity-60" />
                <p className="text-xs">Fetching task execution log...</p>
              </div>
            ) : error || !logDetail ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted-foreground p-8 text-center">
                <FileText className="size-8 opacity-30 text-primary mb-1" />
                <p className="font-bold text-foreground text-sm">No execution logs recorded yet</p>
                <p className="text-xs max-w-md">
                  Logs will appear once a worker node claims and finishes or fails rendering this task chunk.
                </p>
              </div>
            ) : activeTab === "full" ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="p-2.5 px-4 bg-background/60 border-b border-border/60 text-[11px] text-muted-foreground flex justify-between items-center">
                  <span>Console Standard Output & Errors</span>
                  <span>{logDetail.log_output ? `${logDetail.log_output.length.toLocaleString()} characters` : "Empty output"}</span>
                </div>
                <pre
                  className={`p-4 font-mono text-xs text-foreground/90 overflow-auto flex-1 leading-relaxed selection:bg-primary/30 ${
                    wrapLines ? "whitespace-pre-wrap break-all" : "whitespace-pre"
                  }`}
                >
                  {logDetail.log_output || "(No output emitted to stdout/stderr)"}
                </pre>
              </div>
            ) : activeTab === "error" ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {logDetail.error_tail ? (
                  <>
                    <div className="p-2.5 px-4 bg-destructive/10 border-b border-destructive/20 text-xs font-semibold text-destructive flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        <AlertTriangle className="size-4" /> Failure Excerpt (Error Tail)
                      </span>
                      <span className="font-mono text-[11px] text-destructive/80 font-normal">
                        Exit Code {logDetail.exit_status}
                      </span>
                    </div>
                    <pre
                      className={`p-4 font-mono text-xs text-destructive-foreground/90 overflow-auto flex-1 leading-relaxed bg-destructive/5 ${
                        wrapLines ? "whitespace-pre-wrap break-all" : "whitespace-pre"
                      }`}
                    >
                      {logDetail.error_tail}
                    </pre>
                  </>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center gap-2 p-8 text-center text-muted-foreground">
                    <CheckCircle2 className="size-8 text-success opacity-80 mb-1" />
                    <p className="font-bold text-foreground text-sm">No error tail recorded</p>
                    <p className="text-xs max-w-sm">
                      This task completed cleanly with exit code 0 or without unhandled exceptions.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              /* Diagnostics Tab */
              <div className="flex-1 p-5 overflow-auto space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div className="space-y-3 p-4 bg-background/50 rounded-lg border border-border/50">
                    <h4 className="font-bold text-foreground flex items-center gap-2 border-b border-border/50 pb-2">
                      <ListTree className="size-4 text-primary" /> Task Information
                    </h4>
                    <div className="space-y-2">
                      <div className="flex justify-between py-1 border-b border-border/30">
                        <span className="text-muted-foreground">Task Name:</span>
                        <span className="font-semibold text-foreground">{logDetail.task_name || "N/A"}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-border/30">
                        <span className="text-muted-foreground">Task ID:</span>
                        <span className="font-mono text-[11px] text-foreground truncate max-w-[180px]" title={logDetail.task}>
                          {logDetail.task}
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-border/30">
                        <span className="text-muted-foreground">Job Name:</span>
                        <span className="font-semibold text-foreground">{logDetail.job_name || "N/A"}</span>
                      </div>
                      <div className="flex justify-between py-1">
                        <span className="text-muted-foreground">Job ID:</span>
                        <span className="font-mono text-[11px] text-foreground truncate max-w-[180px]" title={logDetail.job}>
                          {logDetail.job}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3 p-4 bg-background/50 rounded-lg border border-border/50">
                    <h4 className="font-bold text-foreground flex items-center gap-2 border-b border-border/50 pb-2">
                      <Server className="size-4 text-info" /> Execution Diagnostics
                    </h4>
                    <div className="space-y-2">
                      <div className="flex justify-between py-1 border-b border-border/30">
                        <span className="text-muted-foreground">Worker Hostname:</span>
                        <span className="font-semibold text-foreground">{logDetail.worker_hostname || "Unknown"}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-border/30">
                        <span className="text-muted-foreground">Exit Status:</span>
                        <span className={`font-semibold ${isSuccess ? "text-success" : "text-destructive"}`}>
                          {logDetail.exit_status} ({isSuccess ? "Success" : "Failed"})
                        </span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-border/30">
                        <span className="text-muted-foreground">Duration:</span>
                        <span className="font-semibold text-foreground">{logDetail.duration_seconds.toFixed(2)} seconds</span>
                      </div>
                      <div className="flex justify-between py-1">
                        <span className="text-muted-foreground">Peak Memory:</span>
                        <span className="font-semibold text-foreground">
                          {logDetail.peak_memory_mb ? `${logDetail.peak_memory_mb} MB` : "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {logDetail.output_image_path && (
                  <div className="p-4 bg-background/50 rounded-lg border border-border/50 text-xs">
                    <h4 className="font-bold text-foreground flex items-center gap-2 mb-2">
                      <ImageIcon className="size-4 text-warning" /> Output Image Artifact
                    </h4>
                    <span className="font-mono text-[11px] text-muted-foreground bg-surface-deep px-2 py-1 rounded block truncate">
                      {logDetail.output_image_path}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        {/* Dialog Footer with Status Info and Action Buttons */}
        <DialogFooter className="border-t border-border/50 px-6 py-3 bg-surface flex flex-row items-center justify-between gap-4 shrink-0 sm:justify-between">
          <div className="text-xs text-muted-foreground font-mono flex items-center gap-2">
            {logDetail ? (
              <>
                <Server className="size-3.5 text-primary shrink-0" />
                <span>
                  Node: <strong className="text-foreground">{logDetail.worker_hostname || "N/A"}</strong>
                </span>
                <span className="text-border">•</span>
                <span>
                  Duration: <strong className="text-foreground">{logDetail.duration_seconds.toFixed(1)}s</strong>
                </span>
              </>
            ) : (
              <span>Execution Inspector</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleRequeue()}
              disabled={isRequeuing || !taskId}
              className="gap-1.5 h-8 px-3 text-xs font-semibold border-amber-500/40 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 hover:text-amber-200"
              title="Requeue this task for execution"
            >
              <RotateCcw className={`size-3.5 ${isRequeuing ? "animate-spin" : ""}`} />
              Requeue Task
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleSkip()}
              disabled={isSkipping || !taskId}
              className="gap-1.5 h-8 px-3 text-xs font-semibold border-destructive/40 bg-destructive/10 text-destructive hover:bg-destructive/20 hover:text-destructive"
              title="Skip this task"
            >
              <SkipForward className={`size-3.5 ${isSkipping ? "animate-spin" : ""}`} />
              Skip Task
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
