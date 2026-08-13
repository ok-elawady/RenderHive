"use client";

import { useMemo, useRef, useEffect } from "react";
import { Brain, RefreshCw, Search, Cpu, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fetchRecentDispatches, type DispatchLogEntry } from "@/services/api";

interface AgenticLogsProps {
  searchQuery: string;
}

function formatTime(isoString: string | null): string {
  if (!isoString) return "--:--";
  return new Date(isoString).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function matchesSearch(entry: DispatchLogEntry, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return [entry.name, entry.job_name, entry.worker_name ?? "", entry.layer_name, entry.ai_reason, entry.state].some(
    (v) => v.toLowerCase().includes(q),
  );
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
      <span className="text-[10px] font-mono shrink-0" style={{ color }}>
        {value.toFixed(3)}
      </span>
    </div>
  );
}

import useSWR from "swr";

export default function AgenticLogs({ searchQuery }: AgenticLogsProps) {
  const terminalRef = useRef<HTMLDivElement | null>(null);
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const {
    data: entries = [],
    error,
    isLoading,
    mutate,
    isValidating,
  } = useSWR<DispatchLogEntry[]>(
    "/api/tasks/recent-dispatches/?limit=30",
    () => fetchRecentDispatches(30),
    {
      refreshInterval: 10000, // Poll every 10 seconds
      revalidateOnFocus: true,
    }
  );

  const fetchError = error ? "Could not reach backend. Real dispatch logs require the API to be online." : null;

  // Scroll to bottom when new entries arrive
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [entries.length]);

  const filteredEntries = useMemo(
    () => entries.filter((e) => matchesSearch(e, normalizedQuery)),
    [entries, normalizedQuery],
  );

  const aiInvokedCount = entries.filter((e) => e.ai_was_invoked).length;

  return (
    <Card className="flex flex-col border-border h-full">
      <CardHeader className="border-b border-border/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <CardTitle className="text-base font-bold text-foreground">Agentic Routing Logs</CardTitle>
            {aiInvokedCount > 0 && (
              <Badge
                variant="outline"
                className="gap-1 text-[10px] h-5 px-1.5 border-primary/40 text-primary bg-primary/5"
              >
                <Brain size={9} />
                {aiInvokedCount} AI
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => void mutate()}
            disabled={isValidating}
            title="Refresh dispatch logs"
          >
            <RefreshCw size={13} className={isValidating ? "animate-spin" : ""} />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col min-h-0">
        <div
          ref={terminalRef}
          className="bg-surface-deep border border-input rounded-lg font-mono text-[11px] leading-relaxed flex-1 h-full overflow-y-auto box-border scroll-smooth"
        >
          {isLoading ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 text-muted-foreground">
              <RefreshCw size={18} className="animate-spin opacity-40" />
              <p className="text-xs">Loading dispatch logs...</p>
            </div>
          ) : fetchError ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center text-center p-4 gap-2">
              <Search size={28} className="mb-1 text-primary opacity-25" />
              <p className="text-xs font-bold text-foreground">No dispatch data available</p>
              <p className="text-[10px] text-muted-foreground">{fetchError}</p>
            </div>
          ) : filteredEntries.length === 0 ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center text-center p-4">
              <Search size={28} className="mb-2 text-primary opacity-25" />
              <p className="text-xs font-bold text-foreground">
                {entries.length === 0 ? "No tasks dispatched yet" : "No matching dispatch events"}
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {entries.length === 0
                  ? "Dispatch logs appear here once workers start claiming tasks."
                  : "Try a different search term."}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border/30">
              {filteredEntries.map((entry) => {
                const bd = entry.last_score_breakdown;
                const baseScore =
                  (bd.job_priority ?? 0) +
                  (bd.resource_fit ?? 0) +
                  (bd.failure_penalty ?? 0) +
                  (bd.dispatch_order ?? 0) +
                  (bd._floor_clamp ?? 0);

                return (
                  <div
                    key={entry.id}
                    className="flex flex-col gap-1.5 px-3 py-2.5 hover:bg-surface-hover transition-colors"
                  >
                    {/* Row 1: time, badges, name */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-muted-foreground opacity-70 shrink-0 tabular-nums">
                        [{formatTime(entry.started_at)}]
                      </span>

                      {entry.ai_was_invoked ? (
                        <Tooltip>
                          <TooltipTrigger>
                            <Badge
                              variant="outline"
                              className="gap-1 text-[10px] h-4 px-1.5 border-primary/40 text-primary bg-primary/5 cursor-help"
                            >
                              <Brain size={8} /> AI
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent side="top" className="max-w-xs text-xs">
                            {entry.ai_reason || "AI tie-breaker was invoked."}
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <Badge
                          variant="outline"
                          className="gap-1 text-[10px] h-4 px-1.5 border-border/50 text-muted-foreground"
                        >
                          <Cpu size={8} /> DET
                        </Badge>
                      )}

                      <span className="text-foreground font-semibold truncate">{entry.job_name}</span>
                      <span className="text-muted-foreground opacity-50">›</span>
                      <span className="text-muted-foreground truncate">{entry.name}</span>
                    </div>

                    {/* Row 2: worker + score bars */}
                    <div className="flex items-center gap-3 flex-wrap pl-1">
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        <span className="opacity-60">→ </span>
                        <span className="text-foreground/70">{entry.worker_name ?? "unknown"}</span>
                      </span>

                      <div className="flex-1 grid grid-cols-2 gap-x-3 gap-y-0.5 min-w-[200px]">
                        <ScoreBar value={baseScore} color="var(--primary)" />
                        {entry.ai_was_invoked && (
                          <ScoreBar
                            value={Math.abs(bd.ai_adjustment ?? 0)}
                            max={0.2}
                            color={(bd.ai_adjustment ?? 0) >= 0 ? "var(--success)" : "var(--destructive)"}
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
      </CardContent>
    </Card>
  );
}
