"use client";

import { useMemo, useState } from "react";
import { Loader2, Clock, Cpu, HardDrive, Monitor } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { PageControlBar } from "@/components/common/PageControlBar";
import { TableSortHeader } from "@/components/common/TableSortHeader";
import type { WorkerNode } from "@/services/api";

function formatMemory(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${mb} MB`;
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Never";

  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) return "Just now";
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`;
  return `${Math.floor(diffInSeconds / 86400)}d ago`;
}

interface NodesTabProps {
  nodes: WorkerNode[];
  isLoading: boolean;
}

export function NodesTab({ nodes, isLoading }: NodesTabProps) {
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const handleSort = (key: string) => {
    setSortConfig((current) => {
      if (current?.key === key) {
        if (current.direction === "asc") return { key, direction: "desc" };
        return null;
      }
      return { key, direction: "asc" };
    });
  };

  const counts = useMemo(
    () => ({
      total: nodes.length,
      online: nodes.filter((n) => n.status === "ONLINE").length,
      rendering: nodes.filter((n) => n.status === "RENDERING").length,
      offline: nodes.filter((n) => n.status === "OFFLINE").length,
    }),
    [nodes],
  );

  const statusChips = [
    { id: "ALL", label: "All Nodes", count: counts.total },
    { id: "ONLINE", label: "Online", count: counts.online },
    { id: "RENDERING", label: "Rendering", count: counts.rendering },
    { id: "OFFLINE", label: "Offline", count: counts.offline },
  ];

  const sortedNodes = useMemo(() => {
    let filtered = nodes;
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (n) =>
          n.hostname.toLowerCase().includes(q) ||
          (n.ip_address && n.ip_address.toLowerCase().includes(q)) ||
          n.pools?.some((p) => p.name.toLowerCase().includes(q)) ||
          n.tags?.some((t) => t.toLowerCase().includes(q)) ||
          n.gpu_models?.some((g) => g.toLowerCase().includes(q)) ||
          (typeof (n.system_info as Record<string, unknown> | undefined)?.cpu_name === "string" &&
            String((n.system_info as Record<string, unknown>).cpu_name).toLowerCase().includes(q)),
      );
    }
    if (statusFilter && statusFilter !== "ALL") {
      filtered = filtered.filter((n) => n.status === statusFilter);
    }

    if (!sortConfig) return filtered;

    return [...filtered].sort((a, b) => {
      let aValue: unknown = a[sortConfig.key as keyof WorkerNode];
      let bValue: unknown = b[sortConfig.key as keyof WorkerNode];

      if (sortConfig.key === "gpu_models") {
        aValue = a.gpu_models?.join(", ") || "";
        bValue = b.gpu_models?.join(", ") || "";
      } else if (sortConfig.key === "pools") {
        aValue = a.pools?.map((p) => p.name).join(", ") || "";
        bValue = b.pools?.map((p) => p.name).join(", ") || "";
      } else if (sortConfig.key === "last_ping") {
        aValue = a.last_ping ? new Date(a.last_ping).getTime() : 0;
        bValue = b.last_ping ? new Date(b.last_ping).getTime() : 0;
      }

      if (aValue === null || aValue === undefined) aValue = "";
      if (bValue === null || bValue === undefined) bValue = "";

      if (typeof aValue === "string") aValue = aValue.toLowerCase();
      if (typeof bValue === "string") bValue = bValue.toLowerCase();

      if ((aValue as string | number) < (bValue as string | number)) return sortConfig.direction === "asc" ? -1 : 1;
      if ((aValue as string | number) > (bValue as string | number)) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [nodes, sortConfig, search, statusFilter]);

  return (
    <div className="flex-1 font-sans h-full flex flex-col space-y-4">
      {/* Page-Level Control Bar */}
      <PageControlBar
        chips={statusChips}
        selectedChip={statusFilter}
        onSelectChip={setStatusFilter}
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search hostname, IP, pool, tag, CPU, or GPU..."
      />

      {/* Main Dedicated Table Card */}
      <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
        <CardContent className="p-0 overflow-x-auto">
          <Table className="table-fixed min-w-[950px]">
            <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
              <TableRow className="hover:bg-transparent bg-muted/30">
                {/* 1. Hostname & IP */}
                <TableHead className="w-[20%] pl-6 text-[11px] uppercase tracking-wider h-8">
                  <TableSortHeader
                    label="Node / IP"
                    sortKey="hostname"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>

                {/* 2. Status */}
                <TableHead className="w-[11%] text-[11px] uppercase tracking-wider h-8">
                  <TableSortHeader
                    label="Status"
                    sortKey="status"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="center"
                  />
                </TableHead>

                {/* 3. Worker Pools */}
                <TableHead className="w-[13%] text-[11px] uppercase tracking-wider h-8">
                  <div className="flex justify-center w-full">
                    <span className="font-semibold text-[11px] text-muted-foreground uppercase tracking-wider">Pools</span>
                  </div>
                </TableHead>

                {/* 4. CPU & RAM (Hardware) */}
                <TableHead className="w-[17%] text-[11px] uppercase tracking-wider h-8">
                  <TableSortHeader
                    label="CPU / Memory"
                    sortKey="cores"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="center"
                  />
                </TableHead>

                {/* 5. GPU Acceleration */}
                <TableHead className="w-[18%] text-[11px] uppercase tracking-wider h-8">
                  <TableSortHeader
                    label="GPU Hardware"
                    sortKey="gpu_models"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>

                {/* 6. Tags */}
                <TableHead className="w-[10%] text-[11px] uppercase tracking-wider h-8">
                  <div className="flex justify-start w-full">
                    <span className="font-semibold text-[11px] text-muted-foreground uppercase tracking-wider">Tags</span>
                  </div>
                </TableHead>

                {/* 7. Last Ping / Heartbeat */}
                <TableHead className="w-[11%] pr-6 text-[11px] uppercase tracking-wider h-8">
                  <TableSortHeader
                    label="Last Ping"
                    sortKey="last_ping"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="right"
                  />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-44 text-center text-muted-foreground">
                    <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                    Loading worker nodes...
                  </TableCell>
                </TableRow>
              ) : sortedNodes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-44 text-center text-muted-foreground">
                    No worker nodes match the selected criteria.
                  </TableCell>
                </TableRow>
              ) : (
                sortedNodes.map((item) => (
                  <TableRow key={item.id} className="group transition-colors hover:bg-muted/40">
                    {/* 1. Hostname & IP */}
                    <TableCell className="pl-6 py-2 text-left">
                      <div className="flex flex-col gap-0.5 min-w-0">
                        <span className="font-bold text-foreground font-mono text-xs truncate" title={item.hostname}>
                          {item.hostname}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono truncate">
                          {item.ip_address || "—"}
                        </span>
                      </div>
                    </TableCell>

                    {/* 2. Status */}
                    <TableCell className="py-2 text-center">
                      <div className="flex justify-center">
                        {item.status === "ONLINE" && (
                          <Badge
                            variant="secondary"
                            className="bg-success/10 text-success border border-success/30 gap-1.5 font-semibold text-[10px] uppercase h-5 px-2"
                          >
                            <div className="size-1.5 rounded-full bg-success animate-pulse" />
                            Online
                          </Badge>
                        )}
                        {item.status === "RENDERING" && (
                          <Badge
                            variant="secondary"
                            className="bg-primary/10 text-primary border border-primary/30 gap-1.5 font-semibold text-[10px] uppercase h-5 px-2"
                          >
                            <Loader2 className="size-2.5 animate-spin" />
                            Rendering
                          </Badge>
                        )}
                        {item.status === "OFFLINE" && (
                          <Badge
                            variant="secondary"
                            className="bg-destructive/10 text-destructive border border-destructive/30 gap-1.5 font-semibold text-[10px] uppercase h-5 px-2"
                          >
                            <div className="size-1.5 rounded-full bg-destructive" />
                            Offline
                          </Badge>
                        )}
                      </div>
                    </TableCell>

                    {/* 3. Pools */}
                    <TableCell className="py-2 text-center">
                      {item.pools && item.pools.length > 0 ? (
                        <div className="flex flex-wrap justify-center gap-1.5">
                          {item.pools.map((pool: { id: string; name: string }) => (
                            <Tooltip key={pool.id}>
                              <TooltipTrigger>
                                <Badge
                                  variant="outline"
                                  className="font-mono text-xs px-2 py-0.5 h-5 border-border bg-muted/30 text-foreground hover:border-primary/50 transition-colors"
                                >
                                  {pool.name}
                                </Badge>
                              </TooltipTrigger>
                              <TooltipContent
                                side="top"
                                className="flex items-center gap-2 px-3 py-1.5 bg-popover text-popover-foreground border border-border shadow-lg rounded-lg text-xs"
                              >
                                <span className="text-muted-foreground font-sans">Pool:</span>
                                <span className="font-semibold text-foreground font-mono">{pool.name}</span>
                              </TooltipContent>
                            </Tooltip>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">Unassigned</span>
                      )}
                    </TableCell>

                    {/* 4. CPU & RAM (Hardware) */}
                    <TableCell className="py-2 text-center">
                      <Tooltip>
                        <TooltipTrigger className="cursor-default inline-block">
                          <div className="flex items-center justify-center gap-1.5 text-xs text-foreground font-mono">
                            <span className="font-semibold text-foreground">{item.cores} cores</span>
                            <span className="text-muted-foreground/60">•</span>
                            <span className="font-semibold text-foreground">{formatMemory(item.memory_mb ?? 0)}</span>
                          </div>
                        </TooltipTrigger>
                        <TooltipContent
                          side="top"
                          className="flex flex-col items-start gap-2 max-w-xs p-3 bg-popover text-popover-foreground border border-border shadow-xl rounded-lg"
                        >
                          <div className="flex items-center gap-2 border-b border-border/60 pb-1.5 w-full">
                            <Cpu size={14} className="text-primary shrink-0" />
                            <span className="font-bold text-xs text-foreground">Hardware Specifications</span>
                          </div>
                          <div className="space-y-1.5 w-full text-xs font-mono">
                            {typeof (item.system_info as Record<string, unknown> | undefined)?.cpu_name === "string" && (
                              <div className="flex flex-col gap-0.5">
                                <span className="text-[11px] text-muted-foreground uppercase tracking-wider font-sans font-semibold">Processor</span>
                                <span className="text-foreground text-xs leading-snug">{String((item.system_info as Record<string, unknown>).cpu_name)}</span>
                              </div>
                            )}
                            <div className="flex items-center justify-between text-xs pt-0.5">
                              <span className="text-muted-foreground font-sans">CPU Cores:</span>
                              <span className="font-semibold text-foreground">{item.cores} Logical</span>
                            </div>
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-muted-foreground font-sans">System Memory:</span>
                              <span className="font-semibold text-foreground">{formatMemory(item.memory_mb ?? 0)}</span>
                            </div>
                          </div>
                        </TooltipContent>
                      </Tooltip>
                    </TableCell>

                    {/* 5. GPU Acceleration & VRAM */}
                    <TableCell className="py-2 text-left">
                      {item.gpu_models && item.gpu_models.length > 0 ? (
                        <Tooltip>
                          <TooltipTrigger className="cursor-default text-left block">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <span className="text-foreground font-medium text-xs truncate max-w-[170px]" title={item.gpu_models.join(", ")}>
                                {item.gpu_models.join(", ")}
                              </span>
                              {typeof (item.system_info as Record<string, unknown> | undefined)?.gpu_vram_mb === "number" && (
                                <span className="text-xs font-mono text-muted-foreground shrink-0">
                                  ({formatMemory((item.system_info as Record<string, unknown>).gpu_vram_mb as number)})
                                </span>
                              )}
                            </div>
                          </TooltipTrigger>
                          <TooltipContent
                            side="top"
                            className="flex flex-col items-start gap-2 max-w-xs p-3 bg-popover text-popover-foreground border border-border shadow-xl rounded-lg"
                          >
                            <div className="flex items-center gap-2 border-b border-border/60 pb-1.5 w-full">
                              <Monitor size={14} className="text-primary shrink-0" />
                              <span className="font-bold text-xs text-foreground">GPU Hardware & VRAM</span>
                            </div>
                            <div className="space-y-2 w-full text-xs font-mono">
                              {Array.isArray((item.system_info as Record<string, unknown> | undefined)?.gpus) && ((item.system_info as Record<string, unknown>).gpus as Array<Record<string, unknown>>).length > 0 ? (
                                ((item.system_info as Record<string, unknown>).gpus as Array<Record<string, unknown>>).map((g, idx) => (
                                  <div key={idx} className="flex flex-col gap-1 bg-muted/40 p-2 rounded border border-border/40">
                                    <div className="flex items-center gap-1.5 text-foreground font-semibold">
                                      <span className="size-1.5 rounded-full bg-primary shrink-0" />
                                      <span className="truncate">{String(g.name || item.gpu_models?.[idx] || "GPU")}</span>
                                    </div>
                                    {typeof g.vram_mb === "number" && (
                                      <div className="flex items-center justify-between text-xs text-muted-foreground pl-3 font-sans">
                                        <span>Total VRAM:</span>
                                        <span className="font-mono text-foreground">{formatMemory(g.vram_mb as number)}</span>
                                      </div>
                                    )}
                                    {item.status !== "OFFLINE" ? (
                                      <>
                                        {typeof g.vram_used_mb === "number" && typeof g.vram_mb === "number" && (
                                          <div className="flex items-center justify-between text-xs text-muted-foreground pl-3 font-sans">
                                            <span>VRAM In Use:</span>
                                            <span className="font-mono text-foreground">
                                              {formatMemory(g.vram_used_mb as number)} ({Math.round(((g.vram_used_mb as number) / (g.vram_mb as number)) * 100)}%)
                                            </span>
                                          </div>
                                        )}
                                        {typeof g.utilization_percent === "number" && (
                                          <div className="flex items-center justify-between text-xs text-muted-foreground pl-3 font-sans">
                                            <span>Core Utilization:</span>
                                            <span className="font-mono text-foreground">{g.utilization_percent}%</span>
                                          </div>
                                        )}
                                      </>
                                    ) : (
                                      <div className="text-xs text-muted-foreground/80 pl-3 font-sans italic pt-0.5">
                                        Offline — Telemetry unavailable
                                      </div>
                                    )}
                                  </div>
                                ))
                              ) : (
                                item.gpu_models.map((gpu, idx) => (
                                  <div key={idx} className="flex items-center justify-between gap-2 bg-muted/40 px-2 py-1 rounded border border-border/40">
                                    <span className="truncate">{gpu}</span>
                                    {typeof (item.system_info as Record<string, unknown> | undefined)?.gpu_vram_mb === "number" && (
                                      <span className="text-muted-foreground font-mono">{formatMemory((item.system_info as Record<string, unknown>).gpu_vram_mb as number)}</span>
                                    )}
                                  </div>
                                ))
                              )}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>

                    {/* 6. Tags */}
                    <TableCell className="py-2 text-left">
                      {item.tags && item.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {item.tags.map((tag) => (
                            <Badge
                              key={tag}
                              variant="outline"
                              className="text-xs px-2 py-0.5 h-5 bg-muted/40 text-foreground font-mono"
                            >
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>

                    {/* 7. Last Ping / Heartbeat */}
                    <TableCell className="pr-6 py-2 text-right">
                      <div className="flex flex-col items-end gap-0.5">
                        <span className="text-xs font-semibold text-foreground flex items-center gap-1">
                          <Clock size={12} className="text-muted-foreground shrink-0" />
                          {formatRelativeTime(item.last_ping)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {new Intl.DateTimeFormat("en", {
                            dateStyle: "short",
                            timeStyle: "short",
                          }).format(new Date(item.last_ping))}
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
