"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  AlertCircle,
  AlertOctagon,
  AlertTriangle,
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
          className="bg-rose-600/20 text-rose-400 border-rose-500/40 text-[11px] font-mono h-5 px-1.5"
        >
          <AlertOctagon className="size-3 mr-1" /> CRIT
        </Badge>
      );
    case "ERROR":
      return (
        <Badge
          variant="destructive"
          className="bg-destructive/15 text-destructive border-destructive/30 text-[11px] font-mono h-5 px-1.5"
        >
          <AlertCircle className="size-3 mr-1" /> ERR
        </Badge>
      );
    case "WARNING":
      return (
        <Badge
          variant="outline"
          className="bg-warning/15 text-warning border-warning/30 text-[11px] font-mono h-5 px-1.5"
        >
          <AlertTriangle className="size-3 mr-1" /> WARN
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="bg-info/10 text-info border-info/30 text-[11px] font-mono h-5 px-1.5">
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
    return allEvents;
  }, [allEvents]);

  return (
    <div className="flex flex-col h-full bg-transparent font-mono">
      <div
        role="region"
        aria-label="Farm Activity Logs"
        aria-live="polite"
        className="text-xs leading-relaxed flex-1 h-full overflow-y-auto box-border scroll-smooth"
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
          <div className="divide-y divide-border/20">
            {filteredEvents.map((evt) => (
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
                          <span className="text-[11px] text-muted-foreground opacity-75">
                            @{evt.actor_username}
                          </span>
                        )}
                        {evt.target_type && evt.target_id && (
                          <span className="text-[11px] text-primary/80 font-mono">
                            {evt.target_type}:{evt.target_id.slice(0, 8)}
                          </span>
                        )}
                      </div>
                      <p className="text-muted-foreground text-xs leading-normal break-words">{evt.message}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                    <span className="text-xs text-muted-foreground opacity-70 tabular-nums">
                      [{formatEventTime(evt.created_at)}]
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
