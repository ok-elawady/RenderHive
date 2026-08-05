"use client";

import { useMemo, useState } from "react";
import {
  Server,
  Loader2,
  HardDrive,
  Clock,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Cpu,
  Layers,
  Search,
  Monitor,
  Network,
  Filter,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
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
  const [statusFilter, setStatusFilter] = useState("");

  const handleSort = (key: string) => {
    setSortConfig((current) => {
      if (current?.key === key) {
        if (current.direction === "asc") return { key, direction: "desc" };
        return null;
      }
      return { key, direction: "asc" };
    });
  };

  const renderSortIcon = (key: string) => {
    if (sortConfig?.key !== key)
      return <ArrowUpDown className="ml-2 size-4 opacity-50 group-hover:opacity-100 transition-opacity" />;
    if (sortConfig.direction === "asc") return <ArrowUp className="ml-2 size-4 text-primary" />;
    return <ArrowDown className="ml-2 size-4 text-primary" />;
  };

  const sortedNodes = useMemo(() => {
    let filtered = nodes;
    if (search) {
      const q = search.toLowerCase();
      filtered = filtered.filter(
        (n) => n.hostname.toLowerCase().includes(q) || (n.ip_address && n.ip_address.toLowerCase().includes(q)),
      );
    }
    if (statusFilter) {
      filtered = filtered.filter((n) => n.status === statusFilter);
    }

    if (!sortConfig) return filtered;

    return [...filtered].sort((a, b) => {
      let aValue: any = a[sortConfig.key as keyof WorkerNode];
      let bValue: any = b[sortConfig.key as keyof WorkerNode];

      if (aValue === null || aValue === undefined) aValue = "";
      if (bValue === null || bValue === undefined) bValue = "";

      if (typeof aValue === "string") aValue = aValue.toLowerCase();
      if (typeof bValue === "string") bValue = bValue.toLowerCase();

      if (aValue < bValue) return sortConfig.direction === "asc" ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [nodes, sortConfig, search, statusFilter]);

  const counts = useMemo(
    () => ({
      total: nodes.length,
      online: nodes.filter((n) => n.status === "ONLINE" || n.status === "RENDERING").length,
      rendering: nodes.filter((n) => n.status === "RENDERING").length,
      offline: nodes.filter((n) => n.status === "OFFLINE").length,
    }),
    [nodes],
  );

  return (
    <div className="flex-1 font-mono h-full flex flex-col">
      <div className="space-y-6">
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Total Nodes
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-foreground">{counts.total}</p>
              <p className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
                <Server size={14} /> Registered machines
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Online
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-success">{counts.online}</p>
              <p className="text-xs font-mono text-success flex items-center gap-1.5">
                <Server size={14} /> Connected
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Rendering
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-primary">{counts.rendering}</p>
              <p className="text-xs font-mono text-primary flex items-center gap-1.5">
                <Cpu size={14} /> Active jobs
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Offline
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-3xl font-black tracking-tight text-destructive">{counts.offline}</p>
              <p className="text-xs font-mono text-destructive flex items-center gap-1.5">
                <Server size={14} /> Disconnected
              </p>
            </CardContent>
          </Card>
        </section>

        <div className="flex items-center justify-between gap-4 mt-8 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by hostname or IP address..."
              className="pl-9 h-10 bg-card border-border/50 shadow-none font-sans"
            />
          </div>
          <Popover>
            <PopoverTrigger
              render={
                <Button
                  variant="outline"
                  className={`h-10 gap-2 px-3 border-border/50 shadow-none bg-card font-sans transition-colors relative ${statusFilter ? "border-primary/50 bg-primary/5 text-primary hover:bg-primary/10" : ""}`}
                />
              }
            >
              <Filter size={16} />
              <span>Filters</span>
              {statusFilter && (
                <span className="absolute -top-2 -right-2 size-5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center ring-2 ring-background">
                  1
                </span>
              )}
            </PopoverTrigger>
            <PopoverContent
              align="end"
              className="w-[240px] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.4)] border border-border/80 bg-popover/85 backdrop-blur-2xl rounded-xl"
            >
              <div className="flex items-center justify-between border-b border-border/50 pb-3">
                <div className="font-semibold text-sm flex items-center gap-2">
                  <Filter size={14} className="text-primary" />
                  Status Filter
                </div>
                {statusFilter && (
                  <button
                    onClick={() => setStatusFilter("")}
                    className="text-[10px] font-medium text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1 bg-muted/40 hover:bg-destructive/10 px-2 py-1 rounded-md"
                  >
                    <X size={10} /> Clear
                  </button>
                )}
              </div>
              <div className="flex flex-col gap-2">
                {["ONLINE", "RENDERING", "OFFLINE"].map((status) => (
                  <Button
                    key={status}
                    variant={statusFilter === status ? "default" : "outline"}
                    size="sm"
                    className="justify-start font-sans"
                    onClick={() => setStatusFilter(statusFilter === status ? "" : status)}
                  >
                    {status === "ONLINE" ? "Online" : status === "RENDERING" ? "Rendering" : "Offline"}
                  </Button>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        </div>

        <Card className="border-border overflow-hidden bg-card/80 backdrop-blur-sm p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader className="bg-muted/30">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[25%] pl-4">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSort("hostname")}
                      className="font-semibold flex items-center group -ml-3"
                    >
                      Hostname
                      {renderSortIcon("hostname")}
                    </Button>
                  </TableHead>
                  <TableHead className="w-[15%]">
                    <div className="flex justify-start w-full pl-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSort("status")}
                        className="font-semibold flex items-center group"
                      >
                        Status
                        {renderSortIcon("status")}
                      </Button>
                    </div>
                  </TableHead>
                  <TableHead className="w-[20%]">
                    <div className="flex justify-start w-full">
                      <span className="font-semibold text-sm py-2 px-3 text-muted-foreground flex items-center">
                        Pools
                      </span>
                    </div>
                  </TableHead>
                  <TableHead className="w-[20%]">
                    <div className="flex justify-start w-full">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSort("cores")}
                        className="font-semibold flex items-center group"
                      >
                        Hardware
                        {renderSortIcon("cores")}
                      </Button>
                    </div>
                  </TableHead>
                  <TableHead className="w-[20%] pr-6">
                    <div className="flex justify-end w-full">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSort("last_ping")}
                        className="font-semibold flex items-center justify-end group"
                      >
                        Last Ping
                        {renderSortIcon("last_ping")}
                      </Button>
                    </div>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                      <Loader2 className="mx-auto mb-2 animate-spin text-primary" size={22} />
                      Loading worker nodes...
                    </TableCell>
                  </TableRow>
                ) : sortedNodes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                      No worker nodes found. Check if the agent is running on any machine.
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedNodes.map((item) => (
                    <TableRow key={item.id} className="group transition-colors hover:bg-muted/40">
                      <TableCell className="pl-6 py-4 text-left">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center gap-2">
                            <Server size={14} className="text-primary" />
                            <span className="font-bold text-foreground">{item.hostname}</span>
                          </div>
                          <div className="flex flex-col gap-1.5 ml-5.5">
                            {item.ip_address && (
                              <span className="text-xs text-muted-foreground flex items-center gap-1">
                                <Network size={12} className="opacity-70" />
                                {item.ip_address}
                              </span>
                            )}
                            {item.tags && item.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-0.5">
                                {item.tags.map((tag) => (
                                  <Badge
                                    key={tag}
                                    variant="secondary"
                                    className="text-[9px] px-1.5 py-0 h-4 bg-muted/50 text-muted-foreground hover:bg-muted font-mono"
                                  >
                                    {tag}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="py-4 pl-5">
                        {item.status === "ONLINE" && (
                          <Badge
                            variant="secondary"
                            className="bg-success/15 text-success hover:bg-success/20 gap-1.5 font-medium"
                          >
                            <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                            Online
                          </Badge>
                        )}
                        {item.status === "RENDERING" && (
                          <Badge
                            variant="secondary"
                            className="bg-primary/15 text-primary hover:bg-primary/20 gap-1.5 font-medium"
                          >
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Rendering
                          </Badge>
                        )}
                        {item.status === "OFFLINE" && (
                          <Badge
                            variant="secondary"
                            className="bg-destructive/15 text-destructive hover:bg-destructive/20 gap-1.5 font-medium"
                          >
                            <div className="w-1.5 h-1.5 rounded-full bg-destructive" />
                            Offline
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="py-4">
                        {item.pools && item.pools.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {item.pools.map((pool: any) => (
                              <TooltipProvider key={pool.id}>
                                <Tooltip>
                                  <TooltipTrigger>
                                    <Badge
                                      variant="outline"
                                      className="font-mono text-[10px] py-0 border-border bg-card"
                                    >
                                      <Layers className="w-3 h-3 mr-1 opacity-50" />
                                      {pool.name}
                                    </Badge>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>Pool: {pool.name}</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell className="py-4">
                        <div className="flex flex-col gap-1.5 text-xs text-muted-foreground">
                          {item.gpu_models && item.gpu_models.length > 0 && (
                            <span className="flex items-start gap-1.5 font-medium text-foreground">
                              <Monitor size={12} className="mt-0.5 text-primary" />
                              <div className="flex flex-col gap-0.5">
                                {item.gpu_models.map((gpu, idx) => (
                                  <span key={idx}>{gpu}</span>
                                ))}
                              </div>
                            </span>
                          )}
                          <span className="flex items-center gap-1.5">
                            <Cpu size={12} className="opacity-70" />
                            {item.cores} cores
                          </span>
                          <span className="flex items-center gap-1.5">
                            <HardDrive size={12} className="opacity-70" />
                            {formatMemory(item.memory_mb ?? 0)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="pr-6 py-4 text-right">
                        <div className="flex flex-col items-end gap-1">
                          <span className="text-sm font-medium flex items-center gap-1.5">
                            <Clock size={12} className="text-muted-foreground" />
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
    </div>
  );
}
