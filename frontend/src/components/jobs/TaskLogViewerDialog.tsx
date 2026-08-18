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
  RefreshCw,
  Server,
  Terminal,
  WrapText,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { fetchTaskExecutionLogLatest } from "@/services/api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type LogTab = "full" | "error" | "diagnostics";

interface TaskLogViewerDialogProps {
  taskId: string | null;
  taskName?: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function TaskLogViewerDialog({
  taskId,
  taskName,
  isOpen,
  onOpenChange,
}: TaskLogViewerDialogProps) {
  const [activeTab, setActiveTab] = useState<LogTab>("full");
  const [wrapLines, setWrapLines] = useState<boolean>(true);

  const {
    data: logDetail,
    isLoading,
    error,
    mutate,
    isValidating,
  } = useSWR(
    taskId && isOpen ? [`/api/telemetry/tasks/logs/latest/`, taskId] : null,
    () => (taskId ? fetchTaskExecutionLogLatest(taskId) : null),
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
        {/* Card Header */}
        <DialogHeader className="border-b border-border/50 px-6 py-4 bg-surface flex flex-row items-center justify-between space-y-0 shrink-0">
          <div className="text-left space-y-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <Terminal className="size-4 text-primary" />
              <DialogTitle className="text-base font-bold text-foreground">
                Task Execution Log: {taskName || logDetail?.task_name || taskId}
              </DialogTitle>
              {logDetail && (
                <Badge
                  variant={isSuccess ? "outline" : "destructive"}
                  className={`text-[10px] font-mono px-2 py-0.5 ${
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
              )}
            </div>
            <DialogDescription className="text-xs text-muted-foreground">
              {logDetail?.job_name ? `Job: ${logDetail.job_name}` : "Process stdout, stderr, and hardware diagnostics."}
            </DialogDescription>
          </div>
        </DialogHeader>

        {/* Card Body */}
        <div className="p-6 space-y-4 flex-1 flex flex-col overflow-hidden">
          {/* Top Toolbar: Tabs on Left, Actions on Right */}
          <div className="flex flex-wrap items-center justify-between gap-3 shrink-0">
            {/* Left: Tab Navigation in Dark Container */}
            <div className="flex items-center gap-1.5 bg-surface-deep border border-border/80 rounded-lg p-1">
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
                  className={`size-3.5 mr-1.5 ${logDetail?.error_tail && !isSuccess ? "text-destructive" : ""}`}
                />
                Error Tail
                {logDetail?.error_tail && !isSuccess && (
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

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              {activeTab !== "diagnostics" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setWrapLines(!wrapLines)}
                  className={`h-8 px-2.5 text-xs border-border bg-surface-deep hover:bg-muted ${
                    wrapLines ? "bg-primary/15 text-primary border-primary/40 font-semibold" : ""
                  }`}
                  title="Toggle line wrapping"
                >
                  <WrapText className="size-3.5 mr-1.5" /> Wrap
                </Button>
              )}
              {activeTab !== "diagnostics" && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleCopyLog}
                  disabled={!logDetail?.log_output && !logDetail?.error_tail}
                  className="h-8 px-3 text-xs bg-primary text-primary-foreground font-bold"
                >
                  <Copy className="size-3.5 mr-1.5" /> Copy Log
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void mutate()}
                disabled={isValidating}
                className="h-8 px-2.5 text-xs border-border bg-surface-deep hover:bg-muted"
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
      </DialogContent>
    </Dialog>
  );
}
