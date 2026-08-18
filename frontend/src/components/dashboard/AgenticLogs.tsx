"use client";

import { useMemo, useRef, useEffect } from "react";
import useSWR from "swr";
import { Brain, Cpu, RefreshCw, Search, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fetchDispatchTraces } from "@/services/api";
import type { DispatchTrace } from "@/types/dashboard";

interface AgenticLogsProps {
  searchQuery?: string;
}

function formatTime(isoString: string | null): string {
  if (!isoString) return "--:--";
  return new Date(isoString).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function matchesSearch(trace: DispatchTrace, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return [
    trace.task_name,
    trace.job_name,
    trace.job_visible_name,
    trace.worker_hostname,
    trace.ai_reason ?? "",
  ].some((v) => v.toLowerCase().includes(q));
}

function ScoreBar({ value, max = 0.65, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <div className="h-1 flex-1 rounded-full bg-muted/60 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono shrink-0" style={{ color }}>
        {value.toFixed(3)}
      </span>
    </div>
  );
}

export default function AgenticLogs({ searchQuery = "" }: AgenticLogsProps) {
  const terminalRef = useRef<HTMLDivElement | null>(null);
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const {
    data: traces = [],
    error,
    isLoading,
    mutate,
    isValidating,
  } = useSWR<DispatchTrace[]>(
    "/api/telemetry/dispatches/?limit=40",
    () => fetchDispatchTraces(40),
    {
      refreshInterval: 8000,
      revalidateOnFocus: true,
    }
  );

  const fetchError = error ? "Could not reach telemetry API." : null;

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [traces.length]);

  const filteredTraces = useMemo(
    () => traces.filter((t) => matchesSearch(t, normalizedQuery)),
    [traces, normalizedQuery]
  );

  const aiInvokedCount = traces.filter((t) => t.ai_invoked).length;

  return (
    <Card className="flex flex-col border-border p-0 gap-0 h-full">
      <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <CardTitle className="text-sm font-bold text-foreground mr-2 flex items-center gap-2.5">
            <Brain size={15} className="text-primary" />
            AI Dispatch Traces
          </CardTitle>
          {aiInvokedCount > 0 && (
            <Badge
              variant="outline"
              className="gap-1 text-[10px] h-5 px-1.5 border-primary/40 text-primary bg-primary/5 font-medium"
            >
              {aiInvokedCount} AI
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0"
          onClick={() => void mutate()}
          disabled={isValidating}
          aria-label="Refresh dispatch logs"
          title="Refresh dispatch logs"
        >
          <RefreshCw size={13} className={isValidating ? "animate-spin" : ""} />
        </Button>
      </CardHeader>

      <CardContent className="p-3.5 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="bg-surface-deep border border-input rounded-lg flex-1 h-full overflow-hidden flex flex-col">
          <div
            ref={terminalRef}
            role="region"
            aria-label="AI Dispatch Logs"
            aria-live="polite"
            className="font-mono text-xs leading-relaxed flex-1 h-full overflow-y-auto box-border scroll-smooth"
          >
            {isLoading && traces.length === 0 ? (
              <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 text-muted-foreground p-6">
                <RefreshCw size={18} className="animate-spin text-primary opacity-60" />
                <p className="text-xs">Loading dispatch traces...</p>
              </div>
            ) : fetchError ? (
              <div className="flex h-full min-h-32 flex-col items-center justify-center text-center p-6 gap-2">
                <Search size={24} className="mb-1 text-destructive opacity-40" />
                <p className="text-xs font-bold text-foreground">No dispatch data available</p>
                <p className="text-xs text-muted-foreground">{fetchError}</p>
              </div>
            ) : filteredTraces.length === 0 ? (
              <div className="flex h-full min-h-32 flex-col items-center justify-center text-center p-6">
                <Search size={24} className="mb-2 text-primary opacity-30" />
                <p className="text-xs font-bold text-foreground">
                  {traces.length === 0 ? "No tasks dispatched yet" : "No matching dispatch events"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {traces.length === 0
                    ? "Dispatch logs appear here once workers claim tasks."
                    : "Try a different search term."}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border/30">
                {filteredTraces.map((trace) => {
                  const bd = (trace.score_breakdown || {}) as Record<string, number>;
                  const baseScore =
                    (bd.job_priority ?? 0) +
                    (bd.resource_fit ?? 0) +
                    (bd.failure_penalty ?? 0) +
                    (bd.dispatch_order ?? 0) +
                    (bd._floor_clamp ?? 0);

                  const aiAdjustment = bd.ai_adjustment ?? 0;

                  return (
                    <div
                      key={trace.id}
                      className="flex flex-col gap-1.5 px-3 py-2.5 hover:bg-surface-hover transition-colors"
                    >
                      {/* Row 1: time, badges, name */}
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-muted-foreground opacity-70 shrink-0 tabular-nums">
                          [{formatTime(trace.dispatched_at)}]
                        </span>

                        {trace.ai_invoked ? (
                          <Tooltip>
                            <TooltipTrigger>
                              <Badge
                                variant="outline"
                                className="gap-1 text-xs h-5 px-2 border-primary/40 text-primary bg-primary/5 cursor-help font-medium"
                              >
                                <Brain size={11} /> AI
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs text-xs font-mono">
                              {trace.ai_reason || "AI tie-breaker adjustment applied."}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <Badge
                            variant="outline"
                            className="gap-1 text-xs h-5 px-2 border-border/50 text-muted-foreground font-medium"
                          >
                            <Cpu size={11} /> DET
                          </Badge>
                        )}

                        {trace.ai_latency_ms !== null && trace.ai_latency_ms !== undefined && (
                          <span className="text-[10px] text-primary/80 font-mono flex items-center gap-0.5 bg-primary/5 px-1.5 py-0.2 rounded">
                            <Zap size={9} /> {trace.ai_latency_ms}ms
                          </span>
                        )}

                        <span className="text-foreground font-semibold truncate">
                          {trace.job_visible_name || trace.job_name}
                        </span>
                        <span className="text-muted-foreground opacity-50">›</span>
                        <span className="text-muted-foreground truncate">{trace.task_name}</span>
                      </div>

                      {/* Row 2: worker + score bars */}
                      <div className="flex items-center gap-3 flex-wrap pl-1">
                        <span className="text-xs text-muted-foreground shrink-0">
                          <span className="opacity-60">→ </span>
                          <span className="text-foreground/80 font-medium">{trace.worker_hostname}</span>
                          {trace.candidate_count > 1 && (
                            <span className="text-[10px] text-muted-foreground ml-1.5 opacity-75">
                              ({trace.candidate_count} candidates)
                            </span>
                          )}
                        </span>

                        <div className="flex-1 grid grid-cols-2 gap-x-3 gap-y-0.5 min-w-[180px]">
                          <ScoreBar value={baseScore} color="var(--primary)" />
                          {trace.ai_invoked && (
                            <ScoreBar
                              value={Math.abs(aiAdjustment)}
                              max={0.2}
                              color={aiAdjustment >= 0 ? "var(--success)" : "var(--destructive)"}
                            />
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
