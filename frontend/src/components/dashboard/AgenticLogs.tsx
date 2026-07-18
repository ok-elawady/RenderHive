"use client";

import { useEffect, useMemo, useRef } from "react";
import { Search } from "lucide-react";
import type { LogEntry } from "@/types/dashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AgenticLogsProps {
  logs: LogEntry[];
  searchQuery: string;
}

function matchesLogSearch(log: LogEntry, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [log.time, log.type, log.msg].some((value) => value.toLowerCase().includes(normalizedQuery));
}

function getLogColor(type: LogEntry["type"]): string {
  if (type === "WARN") return "text-destructive border-destructive/50";
  if (type === "INFO") return "text-success border-success/50";
  return "text-primary border-primary/50";
}

export default function AgenticLogs({ logs, searchQuery }: AgenticLogsProps) {
  const terminalRef = useRef<HTMLDivElement | null>(null);
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const filteredLogs = useMemo<LogEntry[]>(
    () => logs.filter((log) => matchesLogSearch(log, normalizedQuery)),
    [logs, normalizedQuery],
  );

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [filteredLogs.length]);

  return (
    <Card className="flex flex-col border-border">
      <CardHeader>
        <CardTitle className="text-base font-bold text-foreground">Agentic Routing Logs</CardTitle>
      </CardHeader>

      <CardContent>
        <div
          ref={terminalRef}
          className="bg-surface-deep border border-input rounded-lg p-4 font-mono text-[11px] leading-relaxed space-y-2 h-44 overflow-y-auto box-border scroll-smooth"
        >
          {filteredLogs.length > 0 ? (
            filteredLogs.map((log, idx) => (
              <div
                key={`${log.time}-${idx}-${log.msg}`}
                className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4 hover:bg-surface-hover px-2 py-1 rounded transition-all"
              >
                <span className="text-muted-foreground opacity-80 shrink-0">[{log.time}]</span>
                <Badge
                  variant="outline"
                  className={`font-black text-[10px] tracking-wider px-1.5 py-0 min-w-[55px] justify-center ${getLogColor(
                    log.type,
                  )}`}
                >
                  {log.type}
                </Badge>
                <span className="text-foreground select-all break-all">{log.msg}</span>
              </div>
            ))
          ) : (
            <div className="flex h-full min-h-32 flex-col items-center justify-center text-center">
              <Search size={28} className="mb-2 text-primary opacity-25" />
              <p className="text-xs font-bold text-foreground">No backend logs available</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
