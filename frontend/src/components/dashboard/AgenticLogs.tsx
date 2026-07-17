"use client";

import { useEffect, useMemo, useRef } from "react";
import { Search } from "lucide-react";
import type { LogEntry } from "@/types/dashboard";

interface AgenticLogsProps {
  logs: LogEntry[];
  searchQuery: string;
}

function matchesLogSearch(log: LogEntry, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [log.time, log.type, log.msg].some((value) =>
    value.toLowerCase().includes(normalizedQuery),
  );
}

function getLogColor(type: LogEntry["type"]): string {
  if (type === "WARN") return "text-destructive";
  if (type === "INFO") return "text-success";
  return "text-primary";
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
    <section className="bg-surface border border-border p-6 rounded-lg space-y-4 shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-primary animate-ping shadow-[0_0_10px] shadow-primary/40"></div>
        <h3 className="text-base font-bold text-foreground">
          Agentic Routing Logs
        </h3>
      </div>

      <div
        ref={terminalRef}
        className="bg-surface-deep border border-input rounded-lg p-4 font-mono text-[11px] leading-relaxed space-y-2 h-44 overflow-y-auto box-border shadow-inner scroll-smooth"
      >
        {filteredLogs.length > 0 ? (
          filteredLogs.map((log, idx) => (
            <div
              key={`${log.time}-${idx}-${log.msg}`}
              className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4 hover:bg-surface-hover px-2 py-0.5 rounded transition-all"
            >
              <span className="text-muted-foreground opacity-80">
                [{log.time}]
              </span>
              <span
                className={`font-black text-[10px] tracking-wider px-1.5 py-0.2 bg-surface rounded border border-border min-w-[55px] text-center ${getLogColor(log.type)}`}
              >
                {log.type}
              </span>
              <span className="text-foreground select-all">
                {log.msg}
              </span>
            </div>
          ))
        ) : (
          <div className="flex h-full min-h-32 flex-col items-center justify-center text-center">
            <Search size={28} className="mb-2 text-primary opacity-25" />
            <p className="text-xs font-bold text-foreground">
              No backend logs available
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
