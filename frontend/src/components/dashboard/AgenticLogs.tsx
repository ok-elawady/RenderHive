"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  Brain,
  Cpu,
  Info,
  RefreshCw,
  Search,
  Server,
  Sparkles,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchDispatchTraces } from "@/services/api";
import type { DispatchTrace } from "@/types/dashboard";
import { cn } from "@/lib/utils";

type DispatchFilter = "ALL" | "AI_OPTIMIZED" | "MOCK_AI" | "HEURISTIC";

interface AgenticLogsProps {
  searchQuery?: string;
  showDetails?: boolean;
}

function formatTime(isoString: string | null): string {
  if (!isoString) return "--:--:--";
  return new Date(isoString).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function isMockTrace(trace: DispatchTrace): boolean {
  const reasonLower = (trace.ai_reason || "").toLowerCase();
  return (
    reasonLower.includes("mock mode") ||
    reasonLower.includes("no model loaded") ||
    reasonLower.includes("only one candidate")
  );
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

export default function AgenticLogs({
  searchQuery = "",
}: AgenticLogsProps) {
  const [selectedFilter, setSelectedFilter] = useState<DispatchFilter>("ALL");
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const {
    data: traces = [],
    error,
    isLoading,
    mutate,
    isValidating,
  } = useSWR<DispatchTrace[]>(
    "/api/telemetry/dispatches/?limit=50",
    () => fetchDispatchTraces(50),
    {
      refreshInterval: 8000,
      revalidateOnFocus: true,
    }
  );

  const fetchError = error ? "Could not reach telemetry API." : null;

  const tabs: Array<{
    id: DispatchFilter;
    label: string;
    count: number;
    icon: React.ComponentType<{ className?: string }>;
  }> = useMemo(() => {
    const aiOptimized = traces.filter((t) => t.ai_invoked && !isMockTrace(t)).length;
    const mockAi = traces.filter((t) => isMockTrace(t)).length;
    const heuristic = traces.filter((t) => !t.ai_invoked && !isMockTrace(t)).length;

    return [
      { id: "ALL", label: "All", count: traces.length, icon: Brain },
      { id: "AI_OPTIMIZED", label: "AI Opt", count: aiOptimized, icon: Sparkles },
      { id: "MOCK_AI", label: "Mock", count: mockAi, icon: Cpu },
      { id: "HEURISTIC", label: "Heur", count: heuristic, icon: Cpu },
    ];
  }, [traces]);

  const filteredTraces = useMemo(() => {
    let list = traces.filter((t) => matchesSearch(t, normalizedQuery));
    if (selectedFilter === "AI_OPTIMIZED") {
      list = list.filter((t) => t.ai_invoked && !isMockTrace(t));
    } else if (selectedFilter === "MOCK_AI") {
      list = list.filter((t) => isMockTrace(t));
    } else if (selectedFilter === "HEURISTIC") {
      list = list.filter((t) => !t.ai_invoked && !isMockTrace(t));
    }
    return list;
  }, [traces, normalizedQuery, selectedFilter]);

  return (
    <Card className="flex flex-col border-border p-0 gap-0 h-full font-sans">
      {/* Header exactly matching FarmActivityFeed */}
      <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between gap-3 bg-muted/10">
        <div className="flex flex-wrap items-center gap-1.5">
          <CardTitle className="text-sm font-bold text-foreground mr-2 flex items-center gap-2">
            <Brain size={15} className="text-primary" />
            AI Dispatch Traces
          </CardTitle>

          {tabs.map((tab) => {
            const isActive = selectedFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSelectedFilter(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer",
                  isActive
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                <span>{tab.label}</span>
                <span
                  className={cn(
                    "text-xs rounded-full px-2 py-0.5 min-w-5 text-center font-mono leading-none",
                    isActive
                      ? "bg-primary-foreground/20 text-primary-foreground font-bold"
                      : "bg-muted text-muted-foreground font-normal"
                  )}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-1.5">
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
        </div>
      </CardHeader>

      <CardContent className="p-3.5 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="bg-surface-deep border border-border/70 rounded-lg flex-1 h-full overflow-hidden flex flex-col">
          <div
            role="region"
            aria-label="AI Dispatch Logs"
            aria-live="polite"
            className="text-xs leading-relaxed flex-1 h-full overflow-y-auto box-border scroll-smooth"
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
                    ? "Dispatch scoring traces appear here in real-time as workers claim tasks."
                    : "Try a different search term or clear the filter."}
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border/40">
                {filteredTraces.map((trace) => {
                  const bd = (trace.score_breakdown || {}) as Record<string, number>;
                  const isMock = isMockTrace(trace);

                  // Calculate Total Raw Score
                  const rawTotal = Object.entries(bd).reduce((sum, [key, val]) => {
                    if (typeof val === "number" && !key.startsWith("_")) {
                      return sum + val;
                    }
                    return sum;
                  }, 0);

                  const aiAdj = typeof bd.ai_adjustment === "number" ? bd.ai_adjustment : 0;

                  return (
                    <div
                      key={trace.id}
                      className="flex flex-col gap-1.5 p-2.5 hover:bg-muted/15 transition-colors"
                    >
                      {/* Line 1: Timestamp, Mode Badge, Latency (Left) + Score Pill (Right) */}
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                          <span className="text-muted-foreground font-mono text-[10px] shrink-0 opacity-75">
                            [{formatTime(trace.dispatched_at)}]
                          </span>

                          {trace.ai_invoked && !isMock ? (
                            <Badge
                              variant="outline"
                              className="gap-1 text-[10px] h-4.5 px-1.5 border-primary/40 text-primary bg-primary/10 font-semibold"
                            >
                              <Brain size={10} /> AI Optimized
                            </Badge>
                          ) : isMock ? (
                            <Badge
                              variant="outline"
                              className="gap-1 text-[10px] h-4.5 px-1.5 border-amber-500/30 text-amber-400/90 bg-amber-500/10 font-medium"
                            >
                              <Cpu size={10} /> Mock AI
                            </Badge>
                          ) : (
                            <Badge
                              variant="outline"
                              className="gap-1 text-[10px] h-4.5 px-1.5 border-border text-muted-foreground font-medium"
                            >
                              <Cpu size={10} /> Heuristic
                            </Badge>
                          )}

                          {trace.ai_latency_ms !== null && trace.ai_latency_ms !== undefined && !isMock && (
                            <span className="text-[10px] text-muted-foreground font-mono flex items-center gap-0.5 bg-muted/50 px-1 py-0.2 rounded border border-border/40">
                              <Zap size={8} className="text-primary" /> {trace.ai_latency_ms}ms
                            </span>
                          )}
                        </div>

                        {/* Right: Score Pill */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border border-border bg-muted/30 text-foreground">
                            Score: {rawTotal.toFixed(2)}
                          </span>

                          {!isMock && aiAdj !== 0 && (
                            <span
                              className={cn(
                                "text-[10px] font-mono font-semibold px-1 py-0.5 rounded border",
                                aiAdj > 0
                                  ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
                                  : "text-rose-400 border-rose-500/30 bg-rose-500/10"
                              )}
                            >
                              AI {aiAdj > 0 ? `+${aiAdj.toFixed(2)}` : aiAdj.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Line 2: Job Name › Task Name (Left) + Assigned Worker (Right) */}
                      <div className="flex items-center justify-between gap-2 min-w-0">
                        <div className="flex items-center gap-1.5 min-w-0 truncate text-xs">
                          <span
                            className="font-semibold text-foreground truncate max-w-[130px] sm:max-w-[180px]"
                            title={trace.job_visible_name || trace.job_name}
                          >
                            {trace.job_visible_name || trace.job_name}
                          </span>
                          <span className="text-muted-foreground opacity-50 shrink-0">›</span>
                          <span
                            className="text-foreground/80 font-mono text-[11px] truncate"
                            title={trace.task_name}
                          >
                            {trace.task_name}
                          </span>
                        </div>

                        {/* Destination Worker */}
                        <div className="flex items-center gap-1 text-[11px] font-mono shrink-0 bg-muted/40 px-1.5 py-0.5 rounded border border-border/50 text-foreground/90">
                          <Server size={11} className="text-muted-foreground" />
                          <span className="font-semibold">{trace.worker_hostname}</span>
                          {trace.candidate_count > 1 && (
                            <span className="text-muted-foreground text-[10px] opacity-75">
                              ({trace.candidate_count})
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Line 3: AI Reasoning Quote or Mock Note */}
                      {trace.ai_reason && (
                        <div
                          className={cn(
                            "pl-2 py-1 pr-1.5 rounded text-[11px] leading-snug font-sans",
                            isMock
                              ? "bg-muted/30 border-l-2 border-border/70 text-muted-foreground"
                              : "bg-primary/5 border-l-2 border-primary text-foreground/90"
                          )}
                        >
                          <span
                            className={cn(
                              "font-semibold text-[10px] mr-1 inline-flex items-center gap-1",
                              isMock ? "text-muted-foreground" : "text-primary"
                            )}
                          >
                            {isMock ? <Info size={10} /> : <Sparkles size={10} />}
                            {isMock ? "Note:" : "AI Decision:"}
                          </span>
                          <span>
                            {isMock
                              ? `${trace.ai_reason} — deterministic heuristic dispatch.`
                              : trace.ai_reason}
                          </span>
                        </div>
                      )}
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
