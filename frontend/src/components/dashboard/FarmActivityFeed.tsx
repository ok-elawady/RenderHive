"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Info,
  Radio,
  RefreshCw,
  Search,
  Terminal,
} from "lucide-react";
import type { FarmEvent } from "@/types/dashboard";
import { fetchFarmEvents } from "@/services/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SeverityFilter = "ALL" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

function getSeverityBadge(severity: string) {
  switch (severity) {
    case "CRITICAL":
      return (
        <Badge
          variant="destructive"
          className="bg-rose-600/20 text-rose-400 border-rose-500/40 text-[10px] font-mono h-5 px-1.5"
        >
          <AlertOctagon className="size-3 mr-1" /> CRIT
        </Badge>
      );
    case "ERROR":
      return (
        <Badge
          variant="destructive"
          className="bg-destructive/15 text-destructive border-destructive/30 text-[10px] font-mono h-5 px-1.5"
        >
          <AlertCircle className="size-3 mr-1" /> ERR
        </Badge>
      );
    case "WARNING":
      return (
        <Badge
          variant="outline"
          className="bg-warning/15 text-warning border-warning/30 text-[10px] font-mono h-5 px-1.5"
        >
          <AlertTriangle className="size-3 mr-1" /> WARN
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="bg-info/10 text-info border-info/30 text-[10px] font-mono h-5 px-1.5">
          <Info className="size-3 mr-1" /> INFO
        </Badge>
      );
  }
}

function formatEventTime(isoString: string): string {
  if (!isoString) return "--:--";
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function FarmActivityFeed() {
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("ALL");
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const {
    data: allEvents = [],
    error,
    isLoading,
    isValidating,
    mutate,
  } = useSWR<FarmEvent[]>(`/api/telemetry/events/?limit=100`, () => fetchFarmEvents(100), {
    refreshInterval: 8000,
    revalidateOnFocus: true,
  });

  const tabs: Array<{
    id: SeverityFilter;
    label: string;
    count: number;
    hasAlert?: boolean;
    icon: React.ComponentType<{ className?: string }>;
  }> = useMemo(() => {
    const infoCount = allEvents.filter((e) => e.severity === "INFO").length;
    const warnCount = allEvents.filter((e) => e.severity === "WARNING").length;
    const errCount = allEvents.filter((e) => e.severity === "ERROR" || e.severity === "CRITICAL").length;
    return [
      { id: "ALL", label: "All", count: allEvents.length, icon: Terminal },
      { id: "INFO", label: "Info", count: infoCount, icon: Info },
      { id: "WARNING", label: "Warn", count: warnCount, icon: AlertTriangle },
      { id: "ERROR", label: "Error", count: errCount, hasAlert: errCount > 0, icon: AlertCircle },
    ];
  }, [allEvents]);

  const filteredEvents = useMemo(() => {
    if (severityFilter === "ALL") return allEvents;
    if (severityFilter === "ERROR") {
      return allEvents.filter((e) => e.severity === "ERROR" || e.severity === "CRITICAL");
    }
    return allEvents.filter((e) => e.severity === severityFilter);
  }, [allEvents, severityFilter]);

  const toggleExpand = (id: string) => {
    setExpandedEventId((prev) => (prev === id ? null : id));
  };

  return (
    <Card className="flex flex-col border-border p-0 gap-0 h-full">
      <CardHeader className="p-3.5 pb-2.5 border-b border-border/50 flex flex-row items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <CardTitle className="text-sm font-bold text-foreground mr-2 flex items-center gap-2.5">
            <Radio size={15} className="text-primary animate-pulse" />
            Farm Activity Stream
          </CardTitle>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = severityFilter === tab.id;
            const hasAlert = tab.hasAlert && tab.count > 0;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSeverityFilter(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer",
                  isActive
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                  hasAlert && !isActive && "text-destructive hover:text-destructive bg-destructive/10",
                )}
              >
                <span>{tab.label}</span>
                <span
                  className={cn(
                    "text-xs rounded-full px-2 py-0.5 min-w-5 text-center font-mono leading-none",
                    isActive
                      ? "bg-primary-foreground/25 text-primary-foreground font-bold"
                      : hasAlert
                        ? "bg-destructive text-destructive-foreground font-bold"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-foreground shrink-0"
          onClick={() => void mutate()}
          disabled={isValidating}
          aria-label="Refresh activity feed"
          title="Refresh activity feed"
        >
          <RefreshCw size={13} className={isValidating ? "animate-spin" : ""} />
        </Button>
      </CardHeader>

      <CardContent className="p-3.5 flex-1 flex flex-col min-h-0">
        <div
          role="region"
          aria-label="Farm Activity Logs"
          aria-live="polite"
          className="bg-surface-deep border border-input rounded-lg font-mono text-xs leading-relaxed flex-1 h-full overflow-y-auto box-border scroll-smooth"
        >
          {isLoading && allEvents.length === 0 ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 text-muted-foreground p-6">
              <RefreshCw size={18} className="animate-spin text-primary opacity-60" />
              <p className="text-xs">Loading farm events...</p>
            </div>
          ) : error ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center text-center p-6 gap-2">
              <Search size={24} className="mb-1 text-destructive opacity-40" />
              <p className="text-xs font-bold text-foreground">Failed to connect to farm events feed</p>
              <p className="text-xs text-muted-foreground">Could not reach backend telemetry service.</p>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center text-center p-6">
              <Search size={24} className="mb-2 text-primary opacity-30" />
              <p className="text-xs font-bold text-foreground">No farm events recorded</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Cluster events such as worker heartbeats, task timeouts, and failovers will stream here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border/30">
              {filteredEvents.map((evt) => {
                const isExpanded = expandedEventId === evt.id;
                const hasPayload = Boolean(
                  evt.payload &&
                  typeof evt.payload === "object" &&
                  Object.keys(evt.payload as Record<string, unknown>).length > 0,
                );

                return (
                  <div
                    key={evt.id}
                    className="flex flex-col gap-1 px-3 py-2.5 hover:bg-surface-hover transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-start gap-2 flex-1 min-w-0">
                        <div className="shrink-0">{getSeverityBadge(evt.severity)}</div>
                        <div className="space-y-0.5 min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-foreground">{evt.event_type}</span>
                            {evt.actor_username && (
                              <span className="text-[10px] text-muted-foreground opacity-75">
                                @{evt.actor_username}
                              </span>
                            )}
                            {evt.target_type && evt.target_id && (
                              <span className="text-[10px] text-primary/80 font-mono">
                                {evt.target_type}:{evt.target_id.slice(0, 8)}
                              </span>
                            )}
                          </div>
                          <p className="text-muted-foreground text-xs leading-normal break-words">{evt.message}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                        <span className="text-[11px] text-muted-foreground opacity-70 tabular-nums">
                          [{formatEventTime(evt.created_at)}]
                        </span>
                        {hasPayload && (
                          <button
                            type="button"
                            onClick={() => toggleExpand(evt.id)}
                            className="text-muted-foreground hover:text-foreground p-0.5 rounded cursor-pointer"
                            title="Inspect JSON payload"
                          >
                            {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Expanded JSON Payload Drawer */}
                    {isExpanded && hasPayload && (
                      <div className="mt-2 p-2.5 bg-background/80 rounded border border-border text-[11px] text-muted-foreground overflow-x-auto">
                        <div className="flex items-center gap-1.5 text-primary mb-1 font-bold text-[10px]">
                          <Terminal className="size-3" /> PAYLOAD
                        </div>
                        <pre className="text-foreground/90 font-mono text-[10px]">
                          {JSON.stringify(evt.payload, null, 2)}
                        </pre>
                      </div>
                    )}
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
