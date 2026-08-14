"use client";

import { useMemo, useState } from "react";
import { Loader2, HardDrive, Clock, Cpu, Monitor, Network } from "lucide-react";

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
        (n) => n.hostname.toLowerCase().includes(q) || (n.ip_address && n.ip_address.toLowerCase().includes(q)),
      );
    }
    if (statusFilter && statusFilter !== "ALL") {
      filtered = filtered.filter((n) => n.status === statusFilter);
    }

    if (!sortConfig) return filtered;

    return [...filtered].sort((a, b) => {
      let aValue: unknown = a[sortConfig.key as keyof WorkerNode];
      let bValue: unknown = b[sortConfig.key as keyof WorkerNode];

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
    <div className="flex-1 font-mono h-full flex flex-col space-y-4">
      {/* Page-Level Control Bar (DRY & Identical to /jobs) */}
      <PageControlBar
        chips={statusChips}
        selectedChip={statusFilter}
        onSelectChip={setStatusFilter}
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search hostname or IP..."
      />

      {/* Main Dedicated Table Card */}
      <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
        <CardContent className="p-0 overflow-hidden">
          <Table className="table-fixed">
            <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
              <TableRow className="hover:bg-transparent bg-muted/30">
                <TableHead className="w-[28%] pl-6">
                  <TableSortHeader
                    label="Hostname / Node"
                    sortKey="hostname"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[14%]">
                  <TableSortHeader
                    label="Status"
                    sortKey="status"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="center"
                  />
                </TableHead>
                <TableHead className="w-[18%]">
                  <div className="flex justify-center w-full">
                    <span className="font-semibold text-xs text-muted-foreground">Pools</span>
                  </div>
                </TableHead>
                <TableHead className="w-[22%]">
                  <TableSortHeader
                    label="Hardware Telemetry"
                    sortKey="cores"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="center"
                  />
                </TableHead>
                <TableHead className="w-[18%] pr-6">
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
                  <TableCell colSpan={5} className="h-44 text-center text-muted-foreground">
                    <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                    Loading worker nodes...
                  </TableCell>
                </TableRow>
              ) : sortedNodes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-44 text-center text-muted-foreground">
                    No worker nodes match the selected criteria.
                  </TableCell>
                </TableRow>
              ) : (
                sortedNodes.map((item) => (
                  <TableRow key={item.id} className="group transition-colors hover:bg-muted/40">
                    {/* Hostname & IP */}
                    <TableCell className="pl-6 py-3 text-left">
                      <div className="flex flex-col gap-1 min-w-0">
                        <span className="font-bold text-foreground truncate">{item.hostname}</span>
                        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                          {item.ip_address && (
                            <span className="flex items-center gap-1">
                              <Network size={11} className="opacity-70" />
                              {item.ip_address}
                            </span>
                          )}
                          {item.tags && item.tags.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {item.tags.map((tag) => (
                                <Badge
                                  key={tag}
                                  variant="secondary"
                                  className="text-[11px] px-2 py-0.5 h-5 bg-muted/60 text-muted-foreground hover:bg-muted font-mono"
                                >
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </TableCell>

                    {/* Status */}
                    <TableCell className="py-3 text-center">
                      <div className="flex justify-center">
                        {item.status === "ONLINE" && (
                          <Badge
                            variant="secondary"
                            className="bg-success/15 text-success hover:bg-success/20 gap-1.5 font-medium text-[11px] h-5 px-2"
                          >
                            <div className="size-1.5 rounded-full bg-success animate-pulse" />
                            Online
                          </Badge>
                        )}
                        {item.status === "RENDERING" && (
                          <Badge
                            variant="secondary"
                            className="bg-primary/15 text-primary hover:bg-primary/20 gap-1.5 font-medium text-[11px] h-5 px-2"
                          >
                            <Loader2 className="size-2.5 animate-spin" />
                            Rendering
                          </Badge>
                        )}
                        {item.status === "OFFLINE" && (
                          <Badge
                            variant="secondary"
                            className="bg-destructive/15 text-destructive hover:bg-destructive/20 gap-1.5 font-medium text-[11px] h-5 px-2"
                          >
                            <div className="size-1.5 rounded-full bg-destructive" />
                            Offline
                          </Badge>
                        )}
                      </div>
                    </TableCell>

                    {/* Pools */}
                    <TableCell className="py-3 text-center">
                      {item.pools && item.pools.length > 0 ? (
                        <div className="flex flex-wrap justify-center gap-1.5">
                          {item.pools.map((pool: { id: string; name: string }) => (
                            <Tooltip key={pool.id}>
                              <TooltipTrigger>
                                <Badge
                                  variant="outline"
                                  className="font-mono text-[11px] px-2 py-0.5 h-5 border-border bg-card hover:border-primary/50 transition-colors"
                                >
                                  {pool.name}
                                </Badge>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>Pool: {pool.name}</p>
                              </TooltipContent>
                            </Tooltip>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">Unassigned</span>
                      )}
                    </TableCell>

                    {/* Hardware */}
                    <TableCell className="py-3 text-center">
                      <div className="flex flex-col items-center gap-1 text-xs text-muted-foreground">
                        {item.gpu_models && item.gpu_models.length > 0 && (
                          <span className="flex items-center gap-1.5 font-medium text-foreground">
                            <Monitor size={12} className="text-primary" />
                            <span className="truncate max-w-[160px]">{item.gpu_models.join(", ")}</span>
                          </span>
                        )}
                        <div className="flex items-center justify-center gap-3 text-[11px]">
                          <span className="flex items-center gap-1">
                            <Cpu size={11} className="opacity-70" />
                            {item.cores} cores
                          </span>
                          <span className="flex items-center gap-1">
                            <HardDrive size={11} className="opacity-70" />
                            {formatMemory(item.memory_mb ?? 0)}
                          </span>
                        </div>
                      </div>
                    </TableCell>

                    {/* Last Ping */}
                    <TableCell className="pr-6 py-3 text-right">
                      <div className="flex flex-col items-end gap-0.5">
                        <span className="text-xs font-medium flex items-center gap-1">
                          <Clock size={11} className="text-muted-foreground" />
                          {formatRelativeTime(item.last_ping)}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {new Intl.DateTimeFormat("en", { dateStyle: "short", timeStyle: "short" }).format(
                            new Date(item.last_ping),
                          )}
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
