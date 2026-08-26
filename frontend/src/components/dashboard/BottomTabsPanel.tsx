"use client";

import { useMemo, useState } from "react";
import { Server, Cpu, HardDrive, Search, CheckCircle2, XCircle, Clock, PlayCircle, Activity, Brain, Zap, ActivityIcon, AlertCircle } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import AgenticLogs from "./AgenticLogs";
import { ClusterConnectionStatus } from "@/components/layout/ClusterConnectionStatus";
import FarmActivityFeed from "./FarmActivityFeed";
import type { WorkerNode } from "@/services/api";
import { cn } from "@/lib/utils";

export interface BottomTabsPanelProps {
  nodes: WorkerNode[];
  totalNodes: number;
  onlineNodes: number;
  totalCores: number;
  farmEfficiency: number;
  latencyMs: number | null;
  isOffline: boolean;
  errorCount?: number;
}

type Tab = "WORKERS" | "EVENTS" | "AI_LOGS";

function getNodeStateBadge(status?: string) {
  const s = status?.toUpperCase() || "OFFLINE";
  switch (s) {
    case "ONLINE":
      return (
        <Badge variant="success" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0 bg-success/15 text-success hover:bg-success/20">
          <CheckCircle2 size={10} /> {s}
        </Badge>
      );
    case "OFFLINE":
      return (
        <Badge variant="destructive" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0 bg-destructive/15 text-destructive hover:bg-destructive/20">
          <XCircle size={10} /> {s}
        </Badge>
      );
    case "RENDERING":
      return (
        <Badge variant="info" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0 bg-info/15 text-info hover:bg-info/20">
          <PlayCircle size={10} /> {s}
        </Badge>
      );
    case "MAINTENANCE":
      return (
        <Badge variant="warning" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0 bg-warning/15 text-warning hover:bg-warning/20">
          <Clock size={10} /> {s}
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1.5 h-5 px-1.5 text-[10px] rounded-full font-bold border-0 bg-muted/60 text-muted-foreground hover:bg-muted">
          <Clock size={10} /> {s}
        </Badge>
      );
  }
}

function formatMemory(mb: number | undefined | null) {
  if (!mb) return "N/A";
  if (mb < 1024) return `${mb} MB`;
  return `${(mb / 1024).toFixed(1)} GB`;
}

function formatRelativeTime(dateString: string | undefined | null) {
  if (!dateString) return "N/A";
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (diffInSeconds < 60) return `${diffInSeconds}s ago`;
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours}h ago`;
  return date.toLocaleDateString();
}

export function BottomTabsPanel({ 
  nodes,
  totalNodes,
  onlineNodes,
  totalCores,
  farmEfficiency,
  latencyMs,
  isOffline,
  errorCount = 0
}: BottomTabsPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>("WORKERS");
  

  const filteredNodes = nodes;

  return (
    <div className="flex flex-col h-full w-full min-h-0 bg-surface-deep border-t border-border/50">
      {/* Header / Tabs / KPI Bar */}
      <div className="h-10 flex items-center justify-between px-2 bg-muted/40 border-b border-border/30 shrink-0">
        
        {/* Left Side: Tabs */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("WORKERS")}
            className={cn(
              "px-3 h-7 rounded flex items-center gap-1.5 text-xs font-semibold transition-colors cursor-pointer border",
              activeTab === "WORKERS" ? "bg-accent border-border text-foreground" : "border-transparent text-muted-foreground hover:bg-background/50 hover:text-foreground"
            )}
          >
            <Server size={12} className={activeTab === "WORKERS" ? "text-primary" : "opacity-70"} />
            Workers
            <Badge variant="secondary" className="ml-1 px-1 py-0 h-4 text-[10px] bg-muted/50">
              {nodes.length}
            </Badge>
          </button>
          
          <button
            onClick={() => setActiveTab("EVENTS")}
            className={cn(
              "px-3 h-7 rounded flex items-center gap-1.5 text-xs font-semibold transition-colors cursor-pointer border",
              activeTab === "EVENTS" ? "bg-accent border-border text-primary" : "border-transparent text-muted-foreground hover:bg-background/50 hover:text-foreground"
            )}
          >
            <Activity size={12} className={activeTab === "EVENTS" ? "text-primary" : "opacity-70"} />
            Events
          </button>
          
          <button
            onClick={() => setActiveTab("AI_LOGS")}
            className={cn(
              "px-3 h-7 rounded flex items-center gap-1.5 text-xs font-semibold transition-colors cursor-pointer border",
              activeTab === "AI_LOGS" ? "bg-accent border-border text-info" : "border-transparent text-muted-foreground hover:bg-background/50 hover:text-foreground"
            )}
          >
            <Brain size={12} className={activeTab === "AI_LOGS" ? "text-info" : "opacity-70"} />
            AI Logs
          </button>

          {errorCount > 0 && (
            <div className="flex items-center gap-1.5 ml-2 px-2 py-0.5 rounded-full bg-destructive/10 text-destructive text-[11px] font-mono font-bold animate-pulse">
              <AlertCircle size={10} /> {errorCount}
            </div>
          )}
        </div>

        
        <div className="flex items-center">
          <ClusterConnectionStatus />
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-hidden relative bg-transparent">
        
        {/* Workers Tab */}
        {activeTab === "WORKERS" && (
          <div className="absolute inset-0 overflow-auto">
            <Table className="relative w-full">
              <TableHeader className="sticky top-0 bg-muted/40 border-b border-border/50 z-10">
                <TableRow className="border-0 hover:bg-transparent">
                  <TableHead className="w-10 text-left text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0">Status</TableHead>
                  <TableHead className="text-center text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0">Hostname</TableHead>
                  <TableHead className="text-center text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0">IP Address</TableHead>
                  <TableHead className="text-center text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0">Pools</TableHead>
                  <TableHead className="text-center text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0">Resources</TableHead>
                  <TableHead className="text-center text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0">GPU</TableHead>
                  <TableHead className="text-right text-[11px] font-bold uppercase tracking-wider text-foreground h-7 py-0 pr-2">Last Ping</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredNodes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center">
                      <div className="flex flex-col items-center justify-center text-muted-foreground">
                        <Server size={24} className="mb-2 opacity-20" />
                        <p className="text-xs">No workers found</p>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredNodes.map(node => {
                    return (
                      <TableRow key={node.id} className="border-border/10 hover:bg-muted/10 transition-colors h-8">
                        <TableCell className="p-1 text-left pl-3 w-[120px]">
                          <div className="flex items-center justify-start">
                            {getNodeStateBadge(node.status)}
                          </div>
                        </TableCell>
                        <TableCell className="p-1 px-4 text-center font-mono text-xs font-medium text-foreground">
                          {node.hostname}
                        </TableCell>
                        <TableCell className="p-1 px-4 text-center font-mono text-[11px] text-foreground">
                          {node.ip_address || "—"}
                        </TableCell>
                        <TableCell className="p-1 px-4">
                          <div className="flex flex-wrap gap-1 justify-center">
                            {node.pools?.length > 0 ? node.pools.map(pool => (
                              <span key={pool.id} className="px-1.5 py-0.5 rounded text-[11px] font-mono bg-muted text-foreground border border-border/50">
                                {pool.name}
                              </span>
                            )) : (
                              <span className="text-[11px] text-foreground italic">None</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="p-1 px-4">
                          <div className="flex items-center justify-center gap-3">
                            <div className="flex items-center gap-1 text-[11px] font-mono text-foreground">
                              <Cpu size={12} className="text-foreground" /> {node.cores || "?"} C
                            </div>
                            <div className="flex items-center gap-1 text-[11px] font-mono text-foreground">
                              <HardDrive size={12} className="text-foreground" /> {formatMemory(node.memory_mb)}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="p-1 px-4 text-center font-mono text-[11px] text-foreground truncate max-w-[120px] mx-auto">
                          {(node.gpu_models?.length || 0) > 0 ? node.gpu_models?.join(", ") : "—"}
                        </TableCell>
                        <TableCell className="p-1 px-4 text-right font-mono text-[11px] text-foreground">
                          {formatRelativeTime(node.last_ping)}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Events Tab */}
        <div className={cn("absolute inset-0 overflow-y-auto no-scrollbar", activeTab === "EVENTS" ? "block" : "hidden")}>
          <FarmActivityFeed />
        </div>
        
        {/* AI Logs Tab */}
        <div className={cn("absolute inset-0 overflow-y-auto no-scrollbar", activeTab === "AI_LOGS" ? "block" : "hidden")}>
          <AgenticLogs />
        </div>

      </div>
    </div>
  );
}
