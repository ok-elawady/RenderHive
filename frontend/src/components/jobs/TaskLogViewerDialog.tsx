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
    if (!logDetail?.log_output) return;
    try {
      await navigator.clipboard.writeText(logDetail.log_output);
      toast.success("Task log copied to clipboard");
    } catch {
      toast.error("Failed to copy log to clipboard");
    }
  };

  const isSuccess = logDetail?.exit_status === 0;

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl sm:max-w-4xl max-h-[88vh] flex flex-col p-0 gap-0 border-border bg-surface shadow-2xl overflow-hidden font-mono">
        <DialogHeader className="border-b border-border/80 px-6 py-4 bg-background/90 flex flex-row items-center justify-between space-y-0 shrink-0">
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

          <div className="flex items-center gap-2 pr-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void mutate()}
              disabled={isValidating}
              className="h-8 px-2 text-xs border-border"
              title="Refresh log"
            >
              <RefreshCw className={`size-3.5 ${isValidating ? "animate-spin" : ""}`} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setWrapLines(!wrapLines)}
              className={`h-8 px-2 text-xs border-border ${wrapLines ? "bg-primary/10 text-primary border-primary/30" : ""}`}
              title="Toggle line wrapping"
            >
              <WrapText className="size-3.5 mr-1" /> Wrap
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleCopyLog}
              disabled={!logDetail?.log_output}
              className="h-8 px-3 text-xs bg-primary text-primary-foreground font-bold"
            >
              <Copy className="size-3.5 mr-1.5" /> Copy Log
            </Button>
          </div>
        </DialogHeader>

        {/* Diagnostics Strip */}
        {logDetail && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 px-6 py-3 bg-surface-deep/60 border-b border-border/50 text-xs shrink-0">
            <div className="flex items-center gap-2">
              <Clock className="size-3.5 text-muted-foreground shrink-0" />
              <div>
                <div className="text-[10px] text-muted-foreground">Duration</div>
                <div className="font-bold text-foreground">{logDetail.duration_seconds.toFixed(1)}s</div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <HardDrive className="size-3.5 text-primary shrink-0" />
              <div>
                <div className="text-[10px] text-muted-foreground">Peak RAM</div>
                <div className="font-bold text-foreground">
                  {logDetail.peak_memory_mb ? `${logDetail.peak_memory_mb} MB` : "N/A"}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Server className="size-3.5 text-info shrink-0" />
              <div>
                <div className="text-[10px] text-muted-foreground">Worker Node</div>
                <div className="font-bold text-foreground truncate max-w-[140px]">
                  {logDetail.worker_hostname || "Unknown"}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Cpu className="size-3.5 text-warning shrink-0" />
              <div>
                <div className="text-[10px] text-muted-foreground">Attempt</div>
                <div className="font-bold text-foreground">
                  {logDetail.attempt_number ? `#${logDetail.attempt_number}` : "#1"}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Tail Banner */}
        {logDetail?.error_tail && !isSuccess && (
          <div className="m-4 mb-0 p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-xs text-destructive shrink-0 space-y-1">
            <div className="flex items-center gap-1.5 font-bold">
              <AlertTriangle className="size-4" /> Failure Excerpt (Error Tail):
            </div>
            <pre className="font-mono text-[11px] whitespace-pre-wrap break-all text-destructive-foreground/90 bg-background/50 p-2 rounded border border-destructive/20">
              {logDetail.error_tail}
            </pre>
          </div>
        )}

        {/* Log Output Body */}
        <div className="flex-1 p-4 overflow-hidden flex flex-col min-h-[300px]">
          {isLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <RefreshCw className="size-5 animate-spin text-primary opacity-60" />
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
          ) : (
            <div className="flex-1 bg-surface-deep border border-input rounded-lg overflow-hidden flex flex-col">
              <div className="p-3 bg-background/80 border-b border-border/60 text-[11px] text-muted-foreground flex justify-between items-center">
                <span>Console Standard Output & Errors</span>
                <span>{logDetail.log_output ? `${logDetail.log_output.length} characters` : "Empty output"}</span>
              </div>
              <pre
                className={`p-4 font-mono text-xs text-foreground/90 overflow-auto flex-1 leading-relaxed selection:bg-primary/30 ${
                  wrapLines ? "whitespace-pre-wrap break-all" : "whitespace-pre"
                }`}
              >
                {logDetail.log_output || "(No output emitted to stdout/stderr)"}
              </pre>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
