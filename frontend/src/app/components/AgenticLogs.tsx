"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import type { LogEntry, LogMessage } from "../types/dashboard";

interface AgenticLogsProps {
  searchQuery: string;
}

const initialLogs: LogEntry[] = [
  {
    time: "18:20:01",
    type: "INFO",
    msg: "RenderHive Engine core initialized successfully.",
    color: "text-[#3DDC84]",
  },
  {
    time: "18:20:05",
    type: "ROUTE",
    msg: "Gateway connection verified with local clusters.",
    color: "text-[#5A1FA6]",
  },
];

const mockMessages: LogMessage[] = [
  {
    type: "INFO",
    msg: "Syncing task data matrices with internal storage.",
    color: "text-[#5A1FA6]",
  },
  {
    type: "ROUTE",
    msg: "Load balancer distributed frame packet #741A to Node-Gamma.",
    color: "text-[#5A1FA6]",
  },
  {
    type: "WARN",
    msg: "Node-Delta VRAM spikes detected (89%). Allocating paging safety files.",
    color: "text-[#FFB84D]",
  },
  {
    type: "INFO",
    msg: "Bucket rendering completed for frame SEQ_014_SH_020_v08 [Chunk 4].",
    color: "text-[#3DDC84]",
  },
  {
    type: "ROUTE",
    msg: "Re-routing queued light pass task to an optimized CPU cluster.",
    color: "text-[#5A1FA6]",
  },
  {
    type: "WARN",
    msg: "Minor latency delay in Node-Beta-04 client response. Retrying ping...",
    color: "text-[#FFB84D]",
  },
];

function matchesLogSearch(log: LogEntry, normalizedQuery: string): boolean {
  if (!normalizedQuery) return true;

  return [log.time, log.type, log.msg].some((value) =>
    value.toLowerCase().includes(normalizedQuery),
  );
}

export default function AgenticLogs({ searchQuery }: AgenticLogsProps) {
  const terminalRef = useRef<HTMLDivElement | null>(null);
  const logTimerRef = useRef<number | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>(initialLogs);
  const normalizedQuery = searchQuery.trim().toLowerCase();

  const filteredLogs = useMemo<LogEntry[]>(
    () => logs.filter((log) => matchesLogSearch(log, normalizedQuery)),
    [logs, normalizedQuery],
  );

  useEffect(() => {
    logTimerRef.current = window.setInterval(() => {
      const now = new Date();
      const timeStr = now.toTimeString().split(" ")[0];
      const randomMsg =
        mockMessages[Math.floor(Math.random() * mockMessages.length)];

      setLogs((prevLogs) => {
        const updatedLogs: LogEntry[] = [
          ...prevLogs,
          { time: timeStr, ...randomMsg },
        ];
        if (updatedLogs.length > 30) updatedLogs.shift();
        return updatedLogs;
      });
    }, 3500);

    return () => {
      if (logTimerRef.current !== null) {
        window.clearInterval(logTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs, filteredLogs.length]);

  return (
    <section className="bg-[#FFFFFF] dark:bg-[#171A24] border border-[#D7DBE3] dark:border-[#343B4D] p-6 rounded-lg space-y-4 shadow-[0_0_24px_rgba(15,23,42,0.08)] dark:shadow-[0_0_24px_rgba(0,0,0,0.22)]">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-[#5A1FA6] animate-ping shadow-[0_0_10px_rgba(90,31,166,0.4)]"></div>
        <h3 className="text-base font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
          Agentic Routing Logs
        </h3>
      </div>

      <div
        ref={terminalRef}
        className="bg-[#F7F8FA] dark:bg-[#11161F] border border-[#D7DBE3] dark:border-[#2A3143] rounded-lg p-4 font-mono text-[11px] leading-relaxed space-y-2 h-44 overflow-y-auto box-border shadow-inner scroll-smooth"
      >
        {filteredLogs.length > 0 ? (
          filteredLogs.map((log, idx) => (
            <div
              key={`${log.time}-${idx}`}
              className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-4 hover:bg-[#F1F3F6] dark:hover:bg-[#1E2433] px-2 py-0.5 rounded transition-all"
            >
              <span className="text-[#9AA1AE] dark:text-[#5F687D]">
                [{log.time}]
              </span>
              <span
                className={`font-black text-[10px] tracking-wider px-1.5 py-0.2 bg-[#FFFFFF] dark:bg-[#1F2330] rounded border border-[#D7DBE3] dark:border-[#343B4D] min-w-[55px] text-center ${log.color}`}
              >
                {log.type}
              </span>
              <span className="text-[#1A1D23] dark:text-[#D7DBE5] select-all">
                {log.msg}
              </span>
            </div>
          ))
        ) : (
          <div className="flex h-full min-h-32 flex-col items-center justify-center text-center">
            <Search size={28} className="mb-2 text-[#5A1FA6] opacity-25" />
            <p className="text-xs font-bold text-[#1A1D23] dark:text-[#F5F7FA]">
              No matching system logs found
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
