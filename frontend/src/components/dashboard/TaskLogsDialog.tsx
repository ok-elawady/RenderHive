"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import ReactMarkdown from "react-markdown";
import useSWR from "swr";
import { fetchTaskExecutionLogs, fetchTaskExecutionLogById, explainTaskLog, fetchAiHealth, type AiHealthStatus } from "@/services/api";
import type { TaskLogList, TaskLogDetail } from "@/types/dashboard";
import { Loader2, Terminal, AlertCircle, Clock, Server, Monitor, Sparkles, X, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface TaskLogsDialogProps {
  taskId: string | null;
  taskName: string | null;
  isOpen: boolean;
  onClose: () => void;
}

function renderColoredLogs(logText: string, logId: string) {
  if (!logText) return null;
  return logText.split('\n').map((line, i) => {
    let colorClass = "text-foreground/90";
    const lower = line.toLowerCase();
    if (lower.includes("error") || lower.includes("failed") || lower.includes("exception") || lower.includes("traceback") || lower.includes("critical")) {
      colorClass = "text-destructive font-bold";
    } else if (lower.includes("warn")) {
      colorClass = "text-warning";
    } else if (lower.includes("info") || lower.includes("success") || lower.includes("done")) {
      colorClass = "text-success";
    } else if (line.trim().startsWith(">") || line.trim().startsWith("$")) {
      colorClass = "text-info";
    }
    return <div key={`${logId}-${i}`} className={colorClass}>{line}</div>;
  });
}

export function TaskLogsDialog({ taskId, taskName, isOpen, onClose }: TaskLogsDialogProps) {
  const [logs, setLogs] = useState<TaskLogList[]>([]);
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null);
  const [logDetail, setLogDetail] = useState<TaskLogDetail | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [isExplaining, setIsExplaining] = useState(false);

  const { data: health, isLoading: isHealthLoading } = useSWR<AiHealthStatus>(
    isOpen ? "/api/v1/health" : null,
    fetchAiHealth,
    { refreshInterval: 15000 }
  );

  const isAiOnline = health?.status === "ok";
  const isModelLoaded = health?.model_loaded === true;
  const isAiReady = isAiOnline && isModelLoaded;

  useEffect(() => {
    if (!isOpen || !taskId) {
      setLogs([]);
      setSelectedLogId(null);
      setLogDetail(null);
      setExplanation(null);
      return;
    }
    const loadLogs = async () => {
      setIsLoadingList(true);
      try {
        const data = await fetchTaskExecutionLogs(taskId);
        setLogs(data);
        if (data.length > 0) {
          setSelectedLogId(data[data.length - 1].id); // Select latest by default
        }
      } catch (err: any) {
        toast.error("Failed to fetch task logs", { description: err.message });
      } finally {
        setIsLoadingList(false);
      }
    };
    loadLogs();
  }, [isOpen, taskId]);

  useEffect(() => {
    if (!selectedLogId) {
      setLogDetail(null);
      return;
    }
    const loadDetail = async () => {
      setIsLoadingDetail(true);
      try {
        const detail = await fetchTaskExecutionLogById(selectedLogId);
        if (detail) {
          setLogDetail(detail);
          setExplanation(detail.ai_explanation || null);
        } else {
          setLogDetail(null);
          setExplanation(null);
          toast.error("Log detail not found.");
        }
      } catch (err: any) {
        toast.error("Failed to load full log", { description: err.message });
      } finally {
        setIsLoadingDetail(false);
      }
    };
    loadDetail();
  }, [selectedLogId]);

  const handleExplain = async (forceRefresh: boolean = false) => {
    if (!logDetail) return;
    // Prefer the short error_tail; fall back to log_output truncated to 3000 chars
    // to avoid blowing up the AI context window with a full verbose log.
    const rawText = logDetail.error_tail || logDetail.log_output || "";
    const textToExplain = rawText.length > 3000 ? rawText.slice(-3000) : rawText;
    if (!textToExplain) {
      toast.error("No log text available to explain.");
      return;
    }
    
    setIsExplaining(true);
    try {
      const expl = await explainTaskLog(textToExplain, logDetail.id, forceRefresh);
      setExplanation(expl);
    } catch (err: any) {
      toast.error("Failed to explain log", { description: err.message });
    } finally {
      setIsExplaining(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="w-[90vw] !max-w-[1400px] max-h-[85vh] h-[85vh] flex flex-col p-0 gap-0 overflow-hidden bg-background border-border shadow-2xl">
        <DialogHeader className="p-4 border-b border-border/50 bg-muted/20 shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Terminal size={18} className="text-primary" />
            Task Execution Logs: {taskName || "Unknown Task"}
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          {/* Top Panel: List of Attempts (Trials) */}
          <div className="border-b border-border/50 flex bg-surface-deep overflow-x-auto no-scrollbar shrink-0 items-center px-2 py-2 gap-2 min-h-[52px]">
            {isLoadingList ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 size={16} className="animate-spin text-muted-foreground" />
              </div>
            ) : logs.length === 0 ? (
              <div className="flex-1 flex items-center justify-center text-muted-foreground text-xs">
                No logs recorded for this task yet.
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {logs.map((log) => {
                  const isSelected = selectedLogId === log.id;
                  const isSuccess = log.exit_status === 0;
                  return (
                    <button
                      key={log.id}
                      onClick={() => setSelectedLogId(log.id)}
                      className={cn(
                        "flex items-center gap-2.5 px-3 py-1.5 rounded-md border transition-colors shrink-0 cursor-pointer",
                        isSelected 
                          ? "bg-primary/10 border-primary/30 text-primary" 
                          : "bg-muted/40 border-border/40 hover:bg-muted text-muted-foreground"
                      )}
                    >
                      <span className="font-bold text-xs whitespace-nowrap">Attempt #{log.attempt_number || "?"}</span>
                      <div className="w-px h-3.5 bg-border/60" />
                      <div className="flex items-center gap-1 text-[11px]">
                        <Server size={10} className="shrink-0" />
                        <span className="truncate max-w-[100px]">{log.worker_hostname || "Unknown"}</span>
                      </div>
                      <div className="w-px h-3.5 bg-border/60" />
                      <div className="flex items-center gap-1 text-[11px]">
                        <Clock size={10} className="shrink-0" />
                        {log.duration_seconds?.toFixed(1) || 0}s
                      </div>
                      <div className="w-px h-3.5 bg-border/60" />
                      <span className={cn("text-[11px] font-mono font-bold", isSuccess ? "text-success" : "text-destructive")}>
                        Exit {log.exit_status}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right Panel: Full Logs */}
          <div className="flex-1 flex flex-col bg-[#0d1117] relative overflow-hidden">
            <div className="p-2 border-b border-border/20 bg-black/40 flex items-center justify-between text-xs font-mono text-muted-foreground shrink-0 z-10">
              <span>Standard Output & Errors</span>
              <div className="flex items-center gap-4">
                {logDetail && (
                  <span className="opacity-70">
                    Peak Mem: {(logDetail.peak_memory_mb || 0).toFixed(1)}MB
                  </span>
                )}
                {logDetail && !explanation && (
                  <TooltipProvider delayDuration={200}>
                    <Tooltip>
                      <TooltipTrigger
                        onClick={() => handleExplain(false)}
                        disabled={isExplaining || (!isHealthLoading && !isAiReady)}
                        className="flex items-center gap-1.5 px-2 py-1 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 rounded transition-colors disabled:opacity-50 font-sans font-semibold cursor-pointer disabled:cursor-not-allowed"
                      >
                        {isExplaining ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                        {isExplaining ? "Explaining..." : !isAiReady && !isHealthLoading ? "AI Offline" : "Explain with AI"}
                      </TooltipTrigger>
                      <TooltipContent side="bottom" align="center" className="flex flex-col p-3 bg-surface border border-border shadow-xl rounded-xl gap-2 font-sans text-xs w-52 z-50" arrowClassName="bg-surface fill-surface border-t border-l border-border">
                        <div className="w-full flex items-center justify-center border-b border-border/60 pb-2 mb-1">
                          <span className="font-bold text-foreground whitespace-nowrap">AI Service Status</span>
                        </div>
                        <div className="flex flex-col gap-2.5 text-muted-foreground pt-1">
                          <div className="flex flex-col gap-0.5">
                            <span className="opacity-70 text-[11px] uppercase tracking-wider">Service</span>
                            <span className={isHealthLoading ? "" : isAiOnline ? "text-emerald-500 font-bold" : "text-destructive font-bold"}>
                              {isHealthLoading ? "Checking..." : isAiOnline ? "Online" : "Offline"}
                            </span>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <span className="opacity-70 text-[11px] uppercase tracking-wider">Model Loaded</span>
                            <span className={isHealthLoading ? "" : isModelLoaded ? "text-emerald-500 font-bold" : "text-destructive font-bold"}>
                              {isHealthLoading ? "Checking..." : isModelLoaded ? "Yes" : "No"}
                            </span>
                          </div>
                          {isModelLoaded && health?.prompt_template && (
                            <div className="flex flex-col gap-0.5">
                              <span className="opacity-70 text-[11px] uppercase tracking-wider">Model Type</span>
                              <span className="text-foreground capitalize">{health.prompt_template}</span>
                            </div>
                          )}
                          {!isAiReady && !isHealthLoading && (
                            <div className="pt-2 mt-1 border-t border-border/40 text-destructive text-[11px] leading-tight flex items-start gap-1">
                              <AlertCircle size={12} className="shrink-0 mt-0.5" />
                              <span>AI service is unreachable or model is not loaded.</span>
                            </div>
                          )}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto font-mono text-xs p-4 no-scrollbar relative">
              {explanation && (
                <div className="mb-4 bg-card border border-border/50 rounded-md overflow-hidden font-sans text-sm shadow-lg flex flex-col">
                  <div className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between bg-muted/10 shrink-0">
                    <div className="text-sm font-bold text-primary flex items-center gap-2">
                      <Sparkles size={16} />
                      AI Explanation
                    </div>
                    <div className="flex items-center gap-2">
                      <button 
                        onClick={() => handleExplain(true)}
                        disabled={isExplaining}
                        className="text-[11px] uppercase font-bold tracking-wider text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 bg-background/50 px-2 py-1 rounded border border-border/50 disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed"
                        title="Re-run AI Analysis"
                      >
                        {isExplaining ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />}
                        {isExplaining ? "Redoing Analysis..." : "Redo"}
                      </button>
                      <button 
                        onClick={() => setExplanation(null)}
                        className="text-muted-foreground hover:text-foreground transition-colors flex items-center justify-center cursor-pointer ml-1"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="p-4 text-foreground/90 leading-relaxed prose prose-sm prose-invert max-w-none bg-primary/5">
                    <ReactMarkdown>{explanation}</ReactMarkdown>
                  </div>
                </div>
              )}
              {isLoadingDetail ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 size={24} className="animate-spin text-muted-foreground opacity-50" />
                </div>
              ) : !selectedLogId ? (
                <div className="flex items-center justify-center h-full text-muted-foreground/50">
                  Select an attempt to view logs
                </div>
              ) : logDetail ? (
                <pre className="whitespace-pre-wrap break-words leading-relaxed">
                  <span className="text-muted-foreground block mb-4 pb-4 border-b border-border/20">
                    {"// Starting log tail for Attempt #" + (logDetail.attempt_number || "?") + "\n"}
                    {"// Worker: " + (logDetail.worker_hostname || "Unknown") + "\n"}
                    {"// Status: Exit " + logDetail.exit_status}
                  </span>
                  {logDetail.log_output ? (
                    renderColoredLogs(logDetail.log_output, logDetail.id)
                  ) : logDetail.error_tail ? (
                    renderColoredLogs(logDetail.error_tail, logDetail.id)
                  ) : (
                    <span className="text-muted-foreground opacity-50 italic">No output recorded.</span>
                  )}
                </pre>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground/50">
                  Failed to load log detail.
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
