"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import {
  AlertCircle,
  Brain,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Copy,
  Cpu,
  Layers,
  Search,
  Server,
  Terminal,
} from "lucide-react";
import type { DispatchTrace } from "@/types/dashboard";
import { fetchDispatchTraces } from "@/services/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { PageControlBar, type FilterChip } from "@/components/common/PageControlBar";
import { TableSortHeader } from "@/components/common/TableSortHeader";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type DispatchFilter = "ALL" | "AI_OPTIMIZED" | "MOCK_AI" | "HEURISTIC";

interface SortConfig {
  key: "dispatched_at" | "mode" | "job_name" | "worker_hostname" | "score" | "ai_latency_ms";
  direction: "asc" | "desc";
}

function formatEventTime(isoString?: string | null): string {
  if (!isoString) return "--:--:--";
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatEventDate(isoString?: string | null): string {
  if (!isoString) return "";
  const date = new Date(isoString);
  return date.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function isMockTrace(trace: DispatchTrace): boolean {
  const reasonLower = (trace.ai_reason || "").toLowerCase();
  return (
    reasonLower.includes("mock mode") ||
    reasonLower.includes("no model loaded") ||
    reasonLower.includes("only one candidate")
  );
}

function getModeBadge(trace: DispatchTrace) {
  const isMock = isMockTrace(trace);
  if (trace.ai_invoked && !isMock) {
    return (
      <Badge
        variant="outline"
        className="gap-1 border-primary/40 text-primary bg-primary/10 text-[11px] font-mono h-5 px-1.5 inline-flex items-center font-semibold"
      >
        <Brain className="size-3" /> AI OPT
      </Badge>
    );
  }
  if (isMock) {
    return (
      <Badge
        variant="outline"
        className="gap-1 border-amber-500/30 text-amber-400 bg-amber-500/10 text-[11px] font-mono h-5 px-1.5 inline-flex items-center font-medium"
      >
        <Cpu className="size-3" /> MOCK
      </Badge>
    );
  }
  return (
    <Badge
      variant="outline"
      className="gap-1 text-muted-foreground border-border text-[11px] font-mono h-5 px-1.5 inline-flex items-center"
    >
      <Cpu className="size-3" /> HEUR
    </Badge>
  );
}

export function DispatchTracesTable() {
  const [selectedFilter, setSelectedFilter] = useState<DispatchFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTrace, setSelectedTrace] = useState<DispatchTrace | null>(null);
  const [hasCopied, setHasCopied] = useState(false);

  // Sorting
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "dispatched_at",
    direction: "desc",
  });

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(25);

  const {
    data: allTraces = [],
    error,
    isLoading,
    isValidating,
  } = useSWR<DispatchTrace[]>(
    "/api/telemetry/dispatches/?limit=100",
    () => fetchDispatchTraces(100),
    {
      refreshInterval: 8000,
      revalidateOnFocus: true,
    }
  );

  const fetchError = error ? "Could not reach backend telemetry service." : null;

  const chips: FilterChip<DispatchFilter>[] = useMemo(() => {
    const aiOptimized = allTraces.filter((t) => t.ai_invoked && !isMockTrace(t)).length;
    const mockAi = allTraces.filter((t) => isMockTrace(t)).length;
    const heuristic = allTraces.filter((t) => !t.ai_invoked && !isMockTrace(t)).length;

    return [
      { id: "ALL", label: "All", count: allTraces.length },
      { id: "AI_OPTIMIZED", label: "AI Optimized", count: aiOptimized },
      { id: "MOCK_AI", label: "Mock AI", count: mockAi },
      { id: "HEURISTIC", label: "Heuristic", count: heuristic },
    ];
  }, [allTraces]);

  const handleSort = (key: string) => {
    setSortConfig((prev) => ({
      key: key as SortConfig["key"],
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const filteredAndSortedTraces = useMemo(() => {
    let result = [...allTraces];

    // Filter by mode
    if (selectedFilter === "AI_OPTIMIZED") {
      result = result.filter((t) => t.ai_invoked && !isMockTrace(t));
    } else if (selectedFilter === "MOCK_AI") {
      result = result.filter((t) => isMockTrace(t));
    } else if (selectedFilter === "HEURISTIC") {
      result = result.filter((t) => !t.ai_invoked && !isMockTrace(t));
    }

    // Search filtering
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter((t) => {
        return (
          t.task_name.toLowerCase().includes(q) ||
          t.job_name.toLowerCase().includes(q) ||
          (t.job_visible_name && t.job_visible_name.toLowerCase().includes(q)) ||
          t.worker_hostname.toLowerCase().includes(q) ||
          (t.ai_reason && t.ai_reason.toLowerCase().includes(q)) ||
          t.id.toLowerCase().includes(q)
        );
      });
    }

    // Sorting
    return [...result].sort((a, b) => {
      let valA: string | number = "";
      let valB: string | number = "";

      if (sortConfig.key === "dispatched_at") {
        valA = new Date(a.dispatched_at || 0).getTime();
        valB = new Date(b.dispatched_at || 0).getTime();
      } else if (sortConfig.key === "mode") {
        valA = a.ai_invoked && !isMockTrace(a) ? "AI" : isMockTrace(a) ? "MOCK" : "HEUR";
        valB = b.ai_invoked && !isMockTrace(b) ? "AI" : isMockTrace(b) ? "MOCK" : "HEUR";
      } else if (sortConfig.key === "job_name") {
        valA = a.job_visible_name || a.job_name;
        valB = b.job_visible_name || b.job_name;
      } else if (sortConfig.key === "worker_hostname") {
        valA = a.worker_hostname;
        valB = b.worker_hostname;
      } else if (sortConfig.key === "ai_latency_ms") {
        valA = a.ai_latency_ms || 0;
        valB = b.ai_latency_ms || 0;
      } else if (sortConfig.key === "score") {
        const aBd = (a.score_breakdown || {}) as Record<string, number>;
        const bBd = (b.score_breakdown || {}) as Record<string, number>;
        valA = Object.entries(aBd).reduce(
          (s, [k, v]) => (typeof v === "number" && !k.startsWith("_") ? s + v : s),
          0
        );
        valB = Object.entries(bBd).reduce(
          (s, [k, v]) => (typeof v === "number" && !k.startsWith("_") ? s + v : s),
          0
        );
      }

      if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
      if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
  }, [allTraces, selectedFilter, searchQuery, sortConfig]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSortedTraces.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const startIndex = (safePage - 1) * pageSize;
  const paginatedTraces = useMemo(() => {
    return filteredAndSortedTraces.slice(startIndex, startIndex + pageSize);
  }, [filteredAndSortedTraces, startIndex, pageSize]);

  const itemStart = filteredAndSortedTraces.length === 0 ? 0 : startIndex + 1;
  const itemEnd = Math.min(startIndex + pageSize, filteredAndSortedTraces.length);

  const handleCopyPayload = (payload: unknown) => {
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    setHasCopied(true);
    toast.success("Payload copied to clipboard");
    setTimeout(() => setHasCopied(false), 2000);
  };

  return (
    <div className="space-y-4 font-sans">
      {/* Page-level Control Bar: Filter Chips on Left, Search on Right */}
      <PageControlBar
        chips={chips}
        selectedChip={selectedFilter}
        onSelectChip={(id) => {
          setSelectedFilter(id);
          setCurrentPage(1);
        }}
        search={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          setCurrentPage(1);
        }}
        searchPlaceholder="Search dispatches, jobs, tasks, hostnames..."
      />

      {/* Dedicated Table Card exactly matching FarmActivityTable */}
      <Card className="flex flex-col border-border p-0 gap-0 overflow-hidden bg-card">
        <CardContent className="p-0 overflow-hidden">
          <Table className="table-fixed">
            <TableHeader className="bg-card sticky top-0 z-10 border-b border-border/50">
              <TableRow className="hover:bg-muted/30 bg-muted/30">
                <TableHead className="w-[11%] pl-6">
                  <TableSortHeader
                    label="Mode"
                    sortKey="mode"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[14%]">
                  <TableSortHeader
                    label="Timestamp"
                    sortKey="dispatched_at"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[20%]">
                  <TableSortHeader
                    label="Job & Task"
                    sortKey="job_name"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[17%]">
                  <TableSortHeader
                    label="Target / Hostname"
                    sortKey="worker_hostname"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[11%]">
                  <TableSortHeader
                    label="Score"
                    sortKey="score"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="w-[21%]">
                  <TableSortHeader
                    label="Reasoning / Decision"
                    sortKey="ai_latency_ms"
                    currentSortKey={sortConfig?.key}
                    currentDirection={sortConfig?.direction}
                    onSort={handleSort}
                    align="left"
                  />
                </TableHead>
                <TableHead className="font-semibold text-right pr-6 w-[6%] text-xs text-muted-foreground">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>

            <TableBody
              className={cn(
                "transition-opacity duration-200 text-xs",
                isValidating && !isLoading && "opacity-60"
              )}
            >
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i} className="hover:bg-transparent">
                    <TableCell className="pl-6 py-3.5">
                      <Skeleton className="h-5 w-16" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-24" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-28" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-24" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-16" />
                    </TableCell>
                    <TableCell className="py-3.5">
                      <Skeleton className="h-5 w-full max-w-[240px]" />
                    </TableCell>
                    <TableCell className="pr-6 py-3.5">
                      <Skeleton className="h-5 w-5 ml-auto" />
                    </TableCell>
                  </TableRow>
                ))
              ) : fetchError ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-36 text-center text-destructive">
                    <AlertCircle size={22} className="mx-auto mb-1.5" />
                    <p className="text-xs font-bold">Failed to load dispatch traces</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{fetchError}</p>
                  </TableCell>
                </TableRow>
              ) : filteredAndSortedTraces.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-36 text-center text-muted-foreground">
                    <Search size={22} className="opacity-30 text-primary mx-auto mb-1.5" />
                    <p className="text-xs font-bold text-foreground">No dispatch traces found</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {searchQuery
                        ? "Try refining your search query."
                        : "Dispatch events will appear here in real-time as workers claim tasks."}
                    </p>
                  </TableCell>
                </TableRow>
              ) : (
                paginatedTraces.map((trace) => {
                  const bd = (trace.score_breakdown || {}) as Record<string, number>;
                  const isMock = isMockTrace(trace);
                  const rawTotal = Object.entries(bd).reduce((sum, [key, val]) => {
                    if (typeof val === "number" && !key.startsWith("_")) {
                      return sum + val;
                    }
                    return sum;
                  }, 0);

                  const aiAdj = typeof bd.ai_adjustment === "number" ? bd.ai_adjustment : 0;

                  return (
                    <TableRow
                      key={trace.id}
                      className="hover:bg-muted/40 transition-colors group cursor-pointer"
                      onClick={() => setSelectedTrace(trace)}
                    >
                      {/* 1. Mode Badge */}
                      <TableCell className="pl-6 py-3.5 text-left align-middle font-medium">
                        {getModeBadge(trace)}
                      </TableCell>

                      {/* 2. Timestamp */}
                      <TableCell className="py-3.5 text-muted-foreground align-middle whitespace-nowrap text-left">
                        <div className="flex flex-col">
                          <span className="font-semibold text-foreground font-mono">
                            {formatEventTime(trace.dispatched_at)}
                          </span>
                          <span className="text-[11px] opacity-70">
                            {formatEventDate(trace.dispatched_at)}
                          </span>
                        </div>
                      </TableCell>

                      {/* 3. Job & Task */}
                      <TableCell className="py-3.5 text-left align-middle truncate text-muted-foreground">
                        <div className="flex flex-col gap-0.5 min-w-0">
                          <span
                            className="font-semibold text-foreground text-xs truncate"
                            title={trace.job_visible_name || trace.job_name}
                          >
                            {trace.job_visible_name || trace.job_name}
                          </span>
                          <span className="text-[11px] font-mono text-muted-foreground truncate">
                            {trace.task_name}
                          </span>
                        </div>
                      </TableCell>

                      {/* 4. Target Host */}
                      <TableCell className="py-3.5 text-left align-middle truncate text-muted-foreground">
                        <div className="flex flex-col gap-0.5 min-w-0">
                          <span className="font-semibold text-foreground font-mono text-xs truncate">
                            {trace.worker_hostname}
                          </span>
                          {trace.candidate_count > 1 && (
                            <span className="text-[11px] text-muted-foreground">
                              {trace.candidate_count} candidates
                            </span>
                          )}
                        </div>
                      </TableCell>

                      {/* 5. Score & Delta */}
                      <TableCell className="py-3.5 text-left align-middle font-mono">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-foreground text-xs">
                            {rawTotal.toFixed(2)}
                          </span>
                          {!isMock && aiAdj !== 0 && (
                            <span
                              className={cn(
                                "text-[11px] font-semibold",
                                aiAdj > 0 ? "text-emerald-400" : "text-rose-400"
                              )}
                            >
                              ({aiAdj > 0 ? `+${aiAdj.toFixed(2)}` : aiAdj.toFixed(2)})
                            </span>
                          )}
                        </div>
                      </TableCell>

                      {/* 6. Reasoning / Decision Message */}
                      <TableCell className="py-3.5 text-left align-middle text-xs max-w-0">
                        <p
                          className="text-foreground/90 leading-relaxed truncate"
                          title={trace.ai_reason || "Deterministic ranking applied."}
                        >
                          {trace.ai_reason || (
                            <span className="text-muted-foreground opacity-50 italic">
                              Deterministic ranking
                            </span>
                          )}
                        </p>
                      </TableCell>

                      {/* 7. Actions: Right Aligned Chevron */}
                      <TableCell className="pr-6 py-3.5 text-right align-middle">
                        <ChevronRight
                          className="ml-auto text-muted-foreground group-hover:text-foreground transition-colors"
                          size={16}
                        />
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>

        {/* Standard Pagination Footer Matching FarmActivityTable 1:1 */}
        {totalPages > 0 && filteredAndSortedTraces.length > 0 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-3 border-t border-border bg-card text-xs text-muted-foreground font-sans">
            {/* Left: Item Range Counter & Page Size Selector */}
            <div className="flex items-center gap-3">
              <span>
                Showing{" "}
                <strong className="text-foreground">{itemStart}</strong>–
                <strong className="text-foreground">{itemEnd}</strong> of{" "}
                <strong className="text-foreground">{filteredAndSortedTraces.length}</strong> traces
              </span>

              <div className="flex items-center gap-1.5 ml-2">
                <span className="text-xs hidden sm:inline">Rows per page:</span>
                <select
                  aria-label="Rows per page"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="h-7 px-2 py-0 text-xs font-mono rounded bg-surface-deep border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>

            {/* Right: Page Navigation Controls */}
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs mr-1">
                Page <strong className="text-foreground">{safePage}</strong> of{" "}
                <strong className="text-foreground">{totalPages}</strong>
              </span>

              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage <= 1}
                  onClick={() => setCurrentPage(1)}
                  title="First page"
                >
                  <ChevronsLeft className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  title="Previous page"
                >
                  <ChevronLeft className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  title="Next page"
                >
                  <ChevronRight className="size-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-7 p-0"
                  disabled={safePage >= totalPages}
                  onClick={() => setCurrentPage(totalPages)}
                  title="Last page"
                >
                  <ChevronsRight className="size-3.5" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Side Sheet Matching FarmActivityTable Layout Exactly */}
      <Sheet open={Boolean(selectedTrace)} onOpenChange={(open) => !open && setSelectedTrace(null)}>
        <SheetContent
          side="right"
          className="w-full border-border bg-card sm:max-w-md md:max-w-lg flex flex-col h-full overflow-hidden p-0 font-sans"
        >
          {Boolean(selectedTrace) && selectedTrace ? (
            <>
              {/* Sheet Header */}
              <SheetHeader className="border-b border-border p-6 shrink-0">
                <SheetTitle className="text-xl font-black text-foreground">
                  {selectedTrace.job_visible_name || selectedTrace.job_name}
                </SheetTitle>
                <SheetDescription className="mt-1.5 leading-relaxed font-mono text-xs text-muted-foreground break-all">
                  Trace ID: {String(selectedTrace.id)}
                </SheetDescription>
              </SheetHeader>

              {/* Sheet Body Content matching FarmActivityTable */}
              <div className="flex-1 overflow-y-auto p-6 flex flex-col space-y-5">
                {/* Severity & Classification Section */}
                <div>
                  <p className="text-xs uppercase text-muted-foreground font-semibold">
                    Dispatch Mode & Evaluation
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {selectedTrace.ai_invoked && !isMockTrace(selectedTrace) ? (
                      <Badge
                        variant="outline"
                        className="gap-1 border-primary/40 text-primary bg-primary/10 font-semibold text-[11px] font-mono h-5 px-1.5 inline-flex items-center"
                      >
                        <Brain className="size-3" /> AI OPTIMIZED
                      </Badge>
                    ) : isMockTrace(selectedTrace) ? (
                      <Badge
                        variant="outline"
                        className="gap-1 border-amber-500/30 text-amber-400 bg-amber-500/10 text-[11px] font-mono h-5 px-1.5 inline-flex items-center font-medium"
                      >
                        <Cpu className="size-3" /> MOCK AI
                      </Badge>
                    ) : (
                      <Badge
                        variant="outline"
                        className="font-mono text-[11px] h-5 px-1.5 inline-flex items-center gap-1 text-muted-foreground"
                      >
                        <Cpu className="size-3" /> HEURISTIC
                      </Badge>
                    )}

                    {selectedTrace.ai_latency_ms !== null && !isMockTrace(selectedTrace) && (
                      <span className="text-xs font-mono text-muted-foreground">
                        ⚡ {selectedTrace.ai_latency_ms}ms latency
                      </span>
                    )}
                  </div>
                </div>

                {/* AI Decision / Scheduler Note Box */}
                {selectedTrace.ai_reason && (
                  <div className="border-t border-border pt-5 space-y-2">
                    <p className="text-xs uppercase text-muted-foreground font-semibold">
                      Scheduler Decision & Reasoning
                    </p>
                    <div className="p-3.5 bg-surface-deep rounded-lg border border-border text-xs font-mono leading-relaxed text-foreground break-words select-text">
                      {selectedTrace.ai_reason}
                    </div>
                  </div>
                )}

                {/* Event Context & References Section */}
                <div className="grid gap-4 border-t border-border pt-5">
                  <div className="flex items-start gap-3">
                    <Layers className="mt-0.5 text-primary shrink-0" size={16} />
                    <div>
                      <p className="text-xs text-muted-foreground">Task Name</p>
                      <p className="mt-1 text-sm font-bold text-foreground font-mono">
                        {selectedTrace.task_name}
                      </p>
                      {selectedTrace.task && (
                        <p className="text-xs font-mono text-muted-foreground mt-0.5 break-all">
                          Task ID: {selectedTrace.task}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <Server className="mt-0.5 text-primary shrink-0" size={16} />
                    <div>
                      <p className="text-xs text-muted-foreground">Target Host / Resource</p>
                      <p className="mt-1 text-sm font-bold text-foreground font-mono">
                        {selectedTrace.worker_hostname}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {selectedTrace.candidate_count} candidate node{selectedTrace.candidate_count !== 1 ? "s" : ""} evaluated
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <CalendarDays className="mt-0.5 text-primary shrink-0" size={16} />
                    <div>
                      <p className="text-xs text-muted-foreground">Dispatched Timestamp</p>
                      <p className="mt-1 text-sm font-mono text-foreground">
                        {formatEventDate(selectedTrace.dispatched_at)} at{" "}
                        {formatEventTime(selectedTrace.dispatched_at)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Scoring Factor Breakdown Table */}
                <div className="border-t border-border pt-5 space-y-2">
                  <p className="text-xs uppercase text-muted-foreground font-semibold">
                    Scoring Factor Breakdown
                  </p>

                  <div className="rounded-lg border border-border overflow-hidden bg-surface-deep">
                    <table className="w-full text-xs font-mono">
                      <thead className="bg-muted/40 border-b border-border text-muted-foreground text-xs">
                        <tr>
                          <th className="text-left px-3 py-2 font-semibold">Factor</th>
                          <th className="text-right px-3 py-2 font-semibold">Contribution</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/50">
                        {Object.entries(
                          (selectedTrace.score_breakdown || {}) as Record<string, unknown>
                        ).map(([key, val]) => {
                          if (typeof val !== "number" || key.startsWith("_")) return null;
                          const label = key
                            .replace(/_/g, " ")
                            .replace(/\b\w/g, (c) => c.toUpperCase());

                          return (
                            <tr key={key} className="hover:bg-muted/20">
                              <td className="px-3 py-2 text-muted-foreground">{label}</td>
                              <td
                                className={cn(
                                  "px-3 py-2 text-right font-bold",
                                  val > 0
                                    ? "text-emerald-400"
                                    : val < 0
                                    ? "text-rose-400"
                                    : "text-muted-foreground"
                                )}
                              >
                                {val > 0 ? `+${val.toFixed(3)}` : val.toFixed(3)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Structured JSON Payload & Diagnostics */}
                {Boolean(
                  selectedTrace.score_breakdown &&
                    typeof selectedTrace.score_breakdown === "object" &&
                    Object.keys(selectedTrace.score_breakdown as Record<string, unknown>).length > 0
                ) && (
                  <div className="border-t border-border pt-5 space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs uppercase text-muted-foreground font-semibold flex items-center gap-1.5">
                        <Terminal size={13} className="text-primary" />
                        Diagnostic Payload
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCopyPayload(selectedTrace.score_breakdown)}
                        className="h-7 px-2.5 text-xs font-mono gap-1.5 bg-surface-deep border-border"
                      >
                        {hasCopied ? (
                          <>
                            <Check size={12} className="text-emerald-500" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            Copy JSON
                          </>
                        )}
                      </Button>
                    </div>

                    <div className="p-3.5 bg-surface-deep rounded-lg border border-border text-xs text-foreground/90 font-mono overflow-x-auto select-text max-h-60 leading-relaxed">
                      <pre className="text-xs">
                        {JSON.stringify(selectedTrace.score_breakdown, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
